# Genome Object Model (GOM) — 架构文档

版本：0.1.0 | 最后更新：2026-06-29

---

## 1. 概述

### 1.1 什么是 GOM

GOM（Genome Object Model）是 Hermes-bacmap 平台的**统一数据标准**，定义所有业务对象的结构、生命周期、版本管理和事件模型。

**核心设计原则**（project.md §4）：

| 原则 | 含义 | GOM 实现 |
|---|---|---|
| Document First | 所有业务对象采用 JSON Document | SQLite JSON 列（payload_json） |
| Event First | 保存完整分析过程 | events 表 + EventType 枚举 |
| Version First | 所有对象必须记录版本 | (object_id, version) 复合主键 |
| Immutable | 分析结果不可覆盖 | delete() 永远 raise + create_new_version() |

### 1.2 为什么需要 GOM

传统生信平台的痛点：

- 固定 Schema 难以适应不同病原及分析流程
- 数据库 schema 变更需要 migration，成本高
- 不同分析步骤的输出格式不统一
- 审计追溯困难（只存最终结果，不存过程）

GOM 的解决方案：

- JSON Document 灵活适配任意分析结果
- Event 流记录完整分析生命周期
- Version + Immutable 保证可追溯
- SQLite 单文件零运维（V1.0 可迁移 PostgreSQL）

---

## 2. 对象类型

所有对象称为 **Genome Object（GO）**，通过 `object_type` 字段区分：

| object_type | 用途 | 示例 | V0.2 状态 |
|---|---|---|---|
| `sample` | 样本元数据 | strain_id, organism, collection_date | ⬜ |
| `analysis` | 一次完整分析的结果 | species, MLST, serotype, AMR, virulence | ✅ |
| `report` | 生成的报告 | HTML/PDF 路径 | ⬜ |
| `workflow` | Snakemake workflow 定义 | rule 列表, 参数, 版本 | ⬜ |
| `plugin` | 插件描述 | tool 名称, 版本 | ⬜ |
| `knowledge` | 知识图谱三元组 | AMR gene-drug-mechanism | ⬜ |
| `task` | 异步任务状态 | running/completed/failed | ⬜ |

当前已实现：`analysis`（通过 `ingest_results.py` 入库）。

---

## 3. 标准 Schema

### 3.1 GenomeObject 核心字段

```
@dataclass(frozen=True)
class GenomeObject:
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `object_id` | str (UUID v4) | ✅ | 全局唯一标识 |
| `object_type` | ObjectType | ✅ | 7 种类型之一 |
| `version` | int (≥1) | ✅ | 版本号，单调递增 |
| `schema_version` | str (semver) | ✅ | GOM schema 版本（当前 "0.1.0"） |
| `created_at` | datetime | ✅ | 创建时间（UTC） |
| `created_by` | str | ✅ | 创建者（如 "salmonella-pipeline"） |
| `payload` | dict[str, Any] | ✅ | 类型特定的内容（见 §3.3） |
| `pipeline_version` | str \| None | ✅ for analysis | Snakemake workflow Git SHA |
| `database_versions` | dict[str, str] | ✅ for analysis | 参考数据库版本 |
| `tool_versions` | dict[str, str] | ✅ for analysis | 生信工具版本 |
| `organism` | str \| None | — | 派生索引字段（如 "Salmonella enterica"） |
| `strain_id` | str \| None | — | 派生索引字段（如 "SAM-TYP-001"） |
| `database_signature` | str \| None | — | 数据库版本拼接哈希 |

### 3.2 校验规则（`__post_init__`）

| 规则 | 触发条件 | 异常 |
|---|---|---|
| object_type 合法 | 字符串必须在 ObjectType 枚举中 | GOMValidationError |
| version ≥ 1 | 整数且 ≥ 1 | GOMValidationError |
| schema_version semver | 匹配 `^\d+\.\d+\.\d+([-+]\w+)?$` | GOMValidationError |
| ANALYSIS 证据链 | object_type=ANALYSIS 时 pipeline_version 非空 + database_versions 非空 | GOMValidationError |
| frozen=True | 任何字段赋值 | FrozenInstanceError |

### 3.3 payload 结构（按 object_type）

#### analysis（已实现）

```json
{
  "strain_id": "SAM-TYP-001",
  "species_verdict": "Salmonella",
  "qc": { "after_filtering": {...}, "before_filtering": {...} },
  "assembly_stats": "file  format  type  num_seqs  sum_len  N50  ...",
  "mlst": "FILE\\tSCHEME\\tST\\taroC\\tdnaN\\t...",
  "serotype": {
    "sistr": "Typhimurium",
    "serogroup": "B",
    "o_antigen": "1,4,[5],12",
    "h1": "i",
    "h2": "1,2"
  },
  "amr": {
    "abricate_card": [{ "GENE": "blaTEM-1", ... }],
    "abricate_vfdb": [{ "GENE": "spiA", ... }]
  },
  "plasmid": {
    "plasmidfinder": [{ "GENE": "IncA/C2_1", ... }]
  },
  "dec": {
    "ectyper": "Name\\tSerotype\\tO_type\\t...",
    "pathotype": "pathotype\\tdetected_markers\\n...",
    "ipaH": "ipaH_negative"
  }
}
```

---

## 4. 版本管理与 Immutable

### 4.1 版本生命周期

```
v1 创建 (create)
  ↓ pipeline 升级或数据库更新
v2 创建 (create_new_version) — 继承元数据 + 新 payload
  ↓ 再次更新
v3 创建 (create_new_version)
  ↓
... 旧版本永不删除，永不修改
```

### 4.2 create_new_version 继承规则

| 字段 | 来源 |
|---|---|
| object_id | 继承（同一样本同一 ID） |
| object_type | 继承 |
| schema_version | 继承 |
| created_by | 继承 |
| organism / strain_id | 继承 |
| version | +1（最新版本号 + 1） |
| created_at | 当前时间 |
| payload | **新传入** |
| pipeline_version | 新传入或继承 |
| database_versions | 新传入或继承 |
| tool_versions | 新传入或继承 |

### 4.3 入库智能去重（`ingest_results.py`）

```
strain_id 已存在？
├── 否 → 创建 v1
├── 是 + pipeline_version 相同 → 跳过（避免重复）
└── 是 + pipeline_version 不同 → 创建新版本（Immutable + Version First）
```

---

## 5. 三元证据链

project.md §4.5 要求每个分析结论必须可追溯。

### 5.1 证据链组成

```
strain_id:          SAM-TYP-001
pipeline_version:   salmonella-workflow-v0.1
database_versions:  CARD 2026-Apr-3, VFDB 2026-Apr-3,
                    PlasmidFinder 2026-Apr-3, PubMLST salmonella_2
tool_versions:      fastp 1.3.5, Shovill 1.1.0, blast 2.17.0+,
                    gmlst 0.1.0, SISTR 1.1.3, abricate 1.4.0
```

### 5.2 数据存储

- `pipeline_version` → genome_objects.pipeline_version 列
- `database_versions` → payload_json 内 `__gom_database_versions` 键
- `tool_versions` → payload_json 内 `__gom_tool_versions` 键

---

## 6. Composite Triplet Schema

学 [GPAS](https://www.medrxiv.org/content/10.64898/2026.02.18.26346517v1.full-text) 论文，防 AMR 基因近邻幻觉。

### 6.1 结构

```
@dataclass(frozen=True)
class CompositeTriplet:
    subject: str              # 基因名
    relation: str             # 关系（如 confers_resistance_to）
    object: str               # 目标（如药物名）
    subject_attributes: dict  # 突变位点、覆盖率、相似度
    relation_conditions: dict # MIC、方法、文献 PMID
    object_attributes: dict   # 药物类别
```

### 6.2 AMR 示例

```json
{
  "subject": "blaCTX-M-15",
  "subject_attributes": {
    "mutation_site": "Promoter -281G>A",
    "coverage": 99.8,
    "identity": 100.0
  },
  "relation": "confers_resistance_to",
  "relation_conditions": {
    "mic": "≥64 μg/mL",
    "method": "in_silico_prediction",
    "evidence_pmid": "12345678"
  },
  "object": "Cefotaxime",
  "object_attributes": {
    "class": "β-lactam/3rd-gen cephalosporin"
  }
}
```

### 6.3 为什么用复合三元组

`blaCTX-M-15` 与 `blaCTX-M-14`、`blaNDM-1` 在 embedding 空间高度接近。复合 schema 在结构层就区分（不同 mutation、不同 drug），让 deterministic verifier 能精确校验。

---

## 7. 事件系统（Event First）

### 7.1 标准事件类型

| event_type | 触发时机 | 示例 payload |
|---|---|---|
| `uploaded` | FASTQ 上传完成 | `{"strain_id": "SAM-TYP-001"}` |
| `qc_finished` | fastp 质控完成 | `{"step": "fastp"}` |
| `assembly_finished` | Shovill 组装完成 | `{"step": "shovill"}` |
| `annotation_finished` | 注释完成 | `{"step": "bakta"}` |
| `amr_finished` | abricate AMR 完成 | `{"step": "abricate"}` |
| `mlst_finished` | gmlst MLST 完成 | `{"step": "gmlst"}` |
| `serotype_finished` | SISTR/ECTyper 完成 | `{"step": "sistr"}` |
| `snp_finished` | snippy SNP 完成 | `{"step": "snippy"}` |
| `report_generated` | 报告生成 | `{"summary_file": "..."}` |
| `analysis_failed` | 分析失败 | `{"error": "OOM"}` |
| `version_created` | 新版本创建 | `{"from_version": 1}` |

### 7.2 事件查询

```python
# 按时间序列查询
events = gos.list_events(object_id, since=None)

# 带时间过滤
from datetime import datetime, timezone
recent = gos.list_events(object_id, since=datetime.now(timezone.utc))
```

---

## 8. 文件产物（FileArtifact）

### 8.1 设计原则

**数据库只存引用，大文件存本地 FS**（project.md §6.2）。

### 8.2 字段

| 字段 | 说明 |
|---|---|
| artifact_id | UUID v4 |
| object_id | 关联的 GO |
| version | 关联的 GO 版本 |
| file_type | fastq / fasta / bam / vcf / gff / report / ... |
| file_path | 本地绝对路径 |
| sha256 | 文件 SHA256 哈希 |
| size_bytes | 文件大小（字节） |

### 8.3 完整性校验

`register_file_artifact()` 在入库时自动校验：
1. 文件存在
2. SHA256 匹配（实时计算 vs 传入值）
3. 文件大小匹配

### 8.4 V1.0+ 迁移

文件路径从本地绝对路径改为 `s3://bucket/key` URI（MinIO）。

---

## 9. SQLite Schema

### 9.1 表结构

```sql
-- 核心对象表
CREATE TABLE genome_objects (
    object_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    version INTEGER NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    organism TEXT,
    strain_id TEXT,
    pipeline_version TEXT,
    database_signature TEXT,
    PRIMARY KEY (object_id, version)
);

-- 全文检索（BM25）
CREATE VIRTUAL TABLE genome_objects_fts USING fts5(
    object_type, organism, strain_id, payload_text
);

-- 事件流
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_payload TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

-- 文件产物引用
CREATE TABLE file_artifacts (
    artifact_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL
);
```

### 9.2 索引

```sql
CREATE INDEX idx_go_type     ON genome_objects(object_type);
CREATE INDEX idx_go_organism ON genome_objects(organism);
CREATE INDEX idx_go_strain   ON genome_objects(strain_id);
CREATE INDEX idx_events_obj  ON events(object_id, timestamp);
CREATE INDEX idx_fa_object   ON file_artifacts(object_id, version);
```

### 9.3 PRAGMA 优化

```sql
PRAGMA journal_mode = WAL;       -- 多读 + 单写不互斥
PRAGMA synchronous = NORMAL;     -- WAL 下仍 corruption-safe
PRAGMA mmap_size = 30000000000;  -- ~28 GB mmap
PRAGMA wal_autocheckpoint = 1000;
PRAGMA temp_store = MEMORY;
PRAGMA foreign_keys = ON;
```

### 9.4 序列化策略

顶层字段（object_id, object_type 等）存储在独立列用于索引。
payload, database_versions, tool_versions 序列化为 JSON 存入 `payload_json`，用 `__gom_` 前缀区分：

```json
{
  "strain_id": "SAM-TYP-001",
  "species_verdict": "Salmonella",
  "__gom_pipeline_version": "salmonella-workflow-v0.1",
  "__gom_database_versions": {"card": "2026-Apr-3", ...},
  "__gom_tool_versions": {"spades": "3.15.4", ...}
}
```

读取时 `_row_to_go()` 自动 pop `__gom_` 前缀字段还原。

---

## 10. GenomeObjectService API

### 10.1 CRUD

| 方法 | 签名 | 说明 |
|---|---|---|
| `create(obj)` | `GenomeObject → GenomeObject` | 创建新对象（v1），校验后插入 |
| `read(object_id, version=1)` | `str, int → GenomeObject` | 按主键读取 |
| `list_by_type(object_type, limit, offset)` | `ObjectType, int, int → list[GenomeObject]` | 按类型列表（最新版本） |
| `list_by_organism(organism, limit, offset)` | `str, int, int → list[GenomeObject]` | 按物种列表 |
| `delete(object_id, version)` | — | **永远 raise GOMImmutableError** |

### 10.2 版本管理

| 方法 | 签名 | 说明 |
|---|---|---|
| `create_new_version(object_id, payload, ...)` | `→ GenomeObject` | 创建新版本（v+1），继承元数据 |
| `get_latest_version(object_id)` | `str → int` | 获取最新版本号 |
| `list_versions(object_id)` | `str → list[GenomeObject]` | 列出所有版本（升序） |

### 10.3 文件产物

| 方法 | 签名 | 说明 |
|---|---|---|
| `register_file_artifact(object_id, version, file_type, file_path, sha256, size_bytes)` | `→ FileArtifact` | 注册文件（含 SHA256 校验） |
| `list_file_artifacts(object_id, version=None)` | `→ list[FileArtifact]` | 列出关联文件 |

### 10.4 事件流

| 方法 | 签名 | 说明 |
|---|---|---|
| `log_event(object_id, event_type, event_payload)` | `→ Event` | 记录事件 |
| `list_events(object_id, since=None)` | `→ list[Event]` | 列出事件（时间序列） |

### 10.5 Context Manager

```python
with GenomeObjectService(Path("data/hermes_bacmap.sqlite")) as gos:
    obj = gos.create(my_genome_object)
    gos.log_event(obj.object_id, "uploaded", {"strain_id": "SAM-001"})
```

---

## 11. 迁移路径：SQLite → PostgreSQL

### 11.1 触发条件

| 条件 | 说明 |
|---|---|
| 并发用户 ≥ 5 | SQLite WAL 单写瓶颈 |
| 元数据规模 > 1 亿行 | 查询性能下降 |
| 复杂多表 JOIN（KG 推理） | 需 PostgreSQL + Apache AGE |
| 向量检索 > 10M | 需 pgvector |

### 11.2 兼容性设计

| SQLite | PostgreSQL | 兼容性 |
|---|---|---|
| `payload_json TEXT` | `payload_json jsonb` | ✅ JSON 通用 |
| `object_id TEXT PRIMARY KEY` | `object_id UUID` | ✅ |
| FTS5 虚拟表 | pg_trgm + tsvector | ⚠️ 需迁移查询 |
| WAL 模式 | MVCC（原生） | ✅ |

迁移工具：`pgloader` 一键迁移。

---

## 12. 错误类型

| 异常 | 触发场景 |
|---|---|
| `GOMValidationError` | Schema 校验失败（object_type/version/schema_version/证据链） |
| `GOMNotFoundError` | 读取不存在的 (object_id, version) |
| `GOMImmutableError` | 尝试覆盖已有 (object_id, version) 或调用 delete() |
| `FrozenInstanceError` | 尝试修改 frozen dataclass 字段 |

---

## 13. 与业界标准对齐

GOM 内部 JSON 可自定义，但 schema 必须可 1:1 映射到：

| 标准 | 映射字段 |
|---|---|
| [GA4GH](https://ga4gh.org/) | object_id → ga4gh identifier |
| [BioSamples](https://www.ebi.ac.uk/biosamples/) (EBI) | sample payload → BioSamples attributes |
| [NCBI Pathogen Detection](https://www.ncbi.nlm.nih.gov/pathogens/) | analysis AMR → AMRFinderPlus output |
| [PulseNet cgMLST](https://www.cdc.gov/pulsenet/) | MLST alleles → cgMLST profile |
| [CARD/ARO Ontology](https://card.mcmaster.ca/) | CompositeTriplet.subject → ARO gene name |

---

## 14. 实际数据统计

当前 SQLite 数据库（`data/hermes_bacmap.sqlite`）：

| 表 | 行数 |
|---|---|
| genome_objects | 7（6 Salmonella + 1 EIEC ANALYSIS） |
| events | 35（每株 5 个生命周期事件） |
| file_artifacts | 63（每株 ~9 个文件产物） |

每株 ANALYSIS 对象平均包含：
- 9 个文件产物（assembly/qc_json/species_blastn/mlst/sistr/amr_card/amr_vfdb/plasmidfinder/summary）
- 5 个事件（uploaded → qc_finished → assembly_finished → amr_finished → report_generated）
- 三元证据链（pipeline_version + database_versions + tool_versions）

---

## 15. 测试覆盖

| 测试文件 | 测试数 | 覆盖范围 |
|---|---|---|
| `test_genome_object_service.py` | 61 | CRUD + 版本 + 文件 + 事件 + 校验 |
| `test_deterministic_verifier.py` | 21 | species + MLST + serotype + AMR 校验 |
| `test_env.py` | 5 | 环境 + 包导入 |
| **总计** | **87** | 全绿 |

---

## 附录 A：完整 Python 类型定义

```python
# src/hermes_bacmap/genome_object_service.py

class ObjectType(str, Enum):
    SAMPLE = "sample"
    ANALYSIS = "analysis"
    REPORT = "report"
    WORKFLOW = "workflow"
    PLUGIN = "plugin"
    KNOWLEDGE = "knowledge"
    TASK = "task"

@dataclass(frozen=True)
class GenomeObject:
    object_id: str
    object_type: ObjectType
    version: int
    schema_version: str
    created_at: datetime
    created_by: str
    payload: dict[str, Any] = field(default_factory=dict)
    pipeline_version: str | None = None
    database_versions: dict[str, str] = field(default_factory=dict)
    tool_versions: dict[str, str] = field(default_factory=dict)
    organism: str | None = None
    strain_id: str | None = None
    database_signature: str | None = None

@dataclass(frozen=True)
class FileArtifact:
    artifact_id: str
    object_id: str
    version: int
    file_type: str
    file_path: str
    sha256: str
    size_bytes: int

@dataclass(frozen=True)
class Event:
    event_id: str
    object_id: str
    event_type: str
    event_payload: dict[str, Any]
    timestamp: datetime

@dataclass(frozen=True)
class CompositeTriplet:
    subject: str
    relation: str
    object: str
    subject_attributes: dict[str, Any] = field(default_factory=dict)
    relation_conditions: dict[str, Any] = field(default_factory=dict)
    object_attributes: dict[str, Any] = field(default_factory=dict)
```

## 附录 B：标准事件生命周期

```
uploaded
  ↓
qc_finished
  ↓
assembly_finished
  ↓
annotation_finished (V0.3+)
  ↓
amr_finished
  ↓
mlst_finished
  ↓
serotype_finished
  ↓
snp_finished (V0.3+)
  ↓
report_generated
  ↓
version_created (如果重新分析)
```
