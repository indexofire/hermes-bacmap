# GOM 数据模型

Genome Object Model（GOM）是平台的**统一数据标准**，定义所有业务对象的结构、生命周期、版本管理与事件模型。基于 SQLite + WAL + FTS5，单文件零运维。本页是速查参考，完整设计文档见 [docs/gom-architecture.md](../gom-architecture.md)。

## 设计原则

| 原则 | 实现 |
|---|---|
| **Document First** | 所有业务对象用 JSON Document，存于 `payload_json` 列 |
| **Event First** | 完整分析过程记入 `events` 表（uploaded → qc → ... → report） |
| **Version First** | `(object_id, version)` 复合主键，版本单调递增 |
| **Immutable** | `delete()` 永远 raise；重复主键 raise；更新只能创建新版本 |

## SQLite 表结构

### 1. genome_objects（核心对象表）

```sql
CREATE TABLE genome_objects (
    object_id TEXT NOT NULL,           -- UUID v4
    object_type TEXT NOT NULL,          -- sample | analysis | report | workflow | ...
    version INTEGER NOT NULL,           -- 单调递增，从 1 开始
    schema_version TEXT NOT NULL,       -- semver "0.1.0"
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    payload_json TEXT NOT NULL,         -- 所有分析结果存于此 JSON
    organism TEXT,                      -- 索引字段（如 "Salmonella enterica"）
    strain_id TEXT,                     -- 索引字段（如 "SAM-TYP-001"）
    pipeline_version TEXT,              -- ANALYSIS 必填（证据链）
    database_signature TEXT,
    PRIMARY KEY (object_id, version)    -- 复合主键 → 版本化 + 不可变
);
```

顶层字段（object_id / object_type / organism 等）存独立列用于索引；payload / database_versions / tool_versions 序列化为 JSON 存入 `payload_json`，用 `__gom_` 前缀区分。

### 2. genome_objects_fts（全文检索虚拟表）

```sql
CREATE VIRTUAL TABLE genome_objects_fts USING fts5(
    object_type, organism, strain_id, payload_text
);
```

支持 BM25 全文检索，是 `bio_search_samples` 工具的底层引擎（字段加权降级兜底 score=1）。

### 3. events（事件流）

```sql
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    event_type TEXT NOT NULL,           -- uploaded | qc_finished | ... | snp_finished
    event_payload TEXT NOT NULL,        -- JSON
    timestamp TEXT NOT NULL
);
```

标准事件生命周期：

```
uploaded → qc_finished → assembly_finished → annotation_finished
  → amr_finished → mlst_finished → serotype_finished
  → snp_finished → report_generated → version_created（若重分析）
```

### 4. file_artifacts（文件产物引用）

```sql
CREATE TABLE file_artifacts (
    artifact_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    file_type TEXT NOT NULL,            -- fastq | fasta | bam | vcf | gff | report
    file_path TEXT NOT NULL,            -- 本地绝对路径（V1.0+ 改 s3:// URI）
    sha256 TEXT NOT NULL,               -- 64 字符 hex，写入时实时校验
    size_bytes INTEGER NOT NULL
);
```

**设计原则**：数据库只存引用，大文件留本地 FS。`register_file_artifact()` 在写入时自动校验文件存在、SHA256 匹配、大小匹配。

## 索引与 PRAGMA

```sql
CREATE INDEX idx_go_type     ON genome_objects(object_type);
CREATE INDEX idx_go_organism ON genome_objects(organism);
CREATE INDEX idx_go_strain   ON genome_objects(strain_id);
CREATE INDEX idx_events_obj  ON events(object_id, timestamp);
CREATE INDEX idx_fa_object   ON file_artifacts(object_id, version);
```

```sql
PRAGMA journal_mode = WAL;          -- 多读 + 单写不互斥
PRAGMA synchronous = NORMAL;        -- WAL 下仍 corruption-safe
PRAGMA mmap_size = 30000000000;     -- ~28 GB mmap
PRAGMA temp_store = MEMORY;
PRAGMA foreign_keys = ON;
```

## GOS 类接口

`GenomeObjectService`（`genome_object_service.py`，644 行）是唯一对外 API：

| 分类 | 方法 | 说明 |
|---|---|---|
| CRUD | `create(obj)` | 创建（重复主键 raise `GOMImmutableError`） |
| | `read(object_id, version)` | 读取特定版本 |
| | `list_by_type(object_type)` | 按类型列最新版本 |
| | `list_by_organism(organism)` | 按物种筛选 |
| | `delete(...)` | **永远 raise**（Immutable） |
| 版本 | `create_new_version(object_id, payload)` | 创建 v+1，继承元数据 |
| | `get_latest_version(object_id)` | 获取最新版本号 |
| | `list_versions(object_id)` | 列出所有版本（升序） |
| 文件 | `register_file_artifact(...)` | 注册文件（含 SHA256 校验） |
| | `list_file_artifacts(object_id)` | 列出关联文件 |
| 事件 | `log_event(object_id, type, payload)` | 记录事件 |
| | `list_events(object_id, since)` | 列出事件（支持时间过滤） |

Context Manager 用法：

```python
from pathlib import Path
from hermes_bacmap.services.genome_object_service import GenomeObjectService

with GenomeObjectService(Path("data/hermes_bacmap.sqlite")) as gos:
    obj = gos.create(my_genome_object)
    gos.log_event(obj.object_id, "uploaded", {"strain_id": "SAM-TYP-001"})
```

## 版本管理与去重

```
strain_id 已存在？
├── 否 → 创建 v1
├── 是 + pipeline_version 相同 → 跳过（⏭️ 避免重复）
└── 是 + pipeline_version 不同 → 创建新版本（Immutable + Version First）
```

`create_new_version` 继承规则：object_id / object_type / schema_version / created_by / organism / strain_id 全部继承；version +1；created_at 取当前；payload 用新传入值。

## 三元证据链

每个 ANALYSIS 对象必须携带三元证据链，满足公卫审计要求：

```
strain_id:          SAM-TYP-001
pipeline_version:   salmonella-workflow-v0.1
database_versions:  CARD 2026-Apr-3, VFDB 2026-Apr-3,
                    PlasmidFinder 2026-Apr-3, PubMLST salmonella_2
tool_versions:      fastp 1.3.5, Shovill 1.1.0, blast 2.17.0+,
                    gmlst 0.1.0, SISTR 1.1.3, abricate 1.4.0
```

存储位置：`pipeline_version` → 独立列；`database_versions` / `tool_versions` → `payload_json` 内 `__gom_` 前缀键。

## Cohort SNP 入库设计

SNP 分析是**多样本（cohort-level）**结果，不能放入 per-sample 对象。解决方案是创建一个 cohort-level ANALYSIS 对象：

```python
GenomeObject(
    object_type="analysis",
    strain_id="cohort:salmonella-snp",        # 去重键前缀
    organism="Salmonella enterica",
    payload={
        "analysis_type": "snp_cohort",
        "samples": ["SAM-TYP-001", "SAM-TYP-002", ...],   # 7 株
        "tree_newick": "(SAM-TYP-001:0.005,...)",
        "pairwise_distances": {"SAM-TYP-001|SAM-TYP-002": 1666, ...},
        "n_snp_sites": 122598,
        "missing_rate": 0.0467,
    },
    pipeline_version="snp-pipeline-v0.3",
)
```

每个样本的 ANALYSIS 对象额外记录 `snp_finished` 事件，payload 含 cohort object_id 引用，建立双向链接。

文件产物注册：

| file_type | 文件 |
|---|---|
| `snp_tree_newick` | `core.treefile` |
| `snp_alignment` | `core_snps.fasta` |
| `iqtree_report` | `core.iqtree` |
| `joint_vcf` | `joint.vcf.gz` |
| `snp_summary` | `snp_summary.json` |

入库命令：

```bash
python scripts/ingest_results.py --all     # 先入库单株
python scripts/ingest_results.py --snp     # 再入库 cohort
```

幂等：相同 pipeline_version 的重复入库会被跳过。

## 错误类型

| 异常 | 触发场景 |
|---|---|
| `GOMValidationError` | Schema 校验失败（object_type / version / schema_version / 证据链） |
| `GOMNotFoundError` | 读取不存在的 (object_id, version) |
| `GOMImmutableError` | 覆盖已有主键或调用 `delete()` |
| `FrozenInstanceError` | 修改 frozen dataclass 字段 |

## 迁移路径

V1.0+ 触发条件：并发用户 ≥5、元数据 >1 亿行、复杂 KG 推理。SQLite → PostgreSQL（`payload_json TEXT` → `jsonb`，FTS5 → `pg_trgm + tsvector`），用 `pgloader` 一键迁移。

完整设计文档（含 CompositeTriplet schema、GA4GH 映射、实际数据统计）见 [docs/gom-architecture.md](../gom-architecture.md)。
