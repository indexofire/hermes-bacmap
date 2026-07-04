# Hermes-bacmap 开发计划（V0.5）

项目代号：Hermes-bacmap
文档版本：V0.5（2026-07-04，engine 抽象层 + 基因组注释 + Web UI + 本地 LLM + mkdocs 文档站）

> **V0.4 → V0.5 关键变更**：(1) engine/ 算法抽象层（800 行，SequenceMatcher + ReadMapper + Registry，移植自 bacmap engine/align.py）；(2) Python 原生基因组注释 genome_annotator.py（pyrodigal + Prokka DBs，替代 Prokka CLI，CDS 预测 100% 等价 Prodigal，sprot 注释 100% 等价 blastp）；(3) Web UI（FastAPI + React SPA，5 页面）；(4) 本地 LLM 支持（Ollama/vLLM/llama.cpp，switch_llm.py 一键切换）；(5) 失败诊断模块 failure_diagnostics.py（9 种错误模式自动识别）；(6) bio_annotate + bio_diagnose 两个新 Hermes tool（18 tools）；(7) P3 Skills 重组（analyze-salmonella → run-pipeline 跨病原通用）；(8) mkdocs 文档站（23 页面，3117 行）；(9) 代码去重 + 审计修复（_PIXI_BIN 统一、sys.path 7→1、ECTyper 965MB DB 清理、96 tests 全绿）。
>
> **V0.3 → V0.4 关键变更**：(1) 物种鉴定统一为 species_identifier（invA/uidA/ipaH/toxR/tlh 合并为 1 个 BLAST DB，4 个 rule → 1 个）；(2) ecoh_serotyper 瘦身（330→121 行，委托 gene_scanner）；(3) shigella_serotyper 移植（ShigATyper 58 种血清型，纯 Python）；(4) gene_scanner 通用 BLAST 引擎（替代 abricate 概念，支持任意数据库）；(5) 血清型分流逻辑（Shigella→shigella_serotyper，DEC/EIEC→ecoh_serotyper）；(6) bio_gene_scan Hermes tool（14 个 tool）。
>
> **V0.2 → V0.3 关键变更**：(1) V0.1 Salmonella MVP 全部完成（6 株端到端 + Hermes 插件 + 87 测试）；(2) 新增靶基因物种鉴定体系：invA(Salmonella) + uidA(E.coli/DEC) + ipaH(Shigella/EIEC)；(3) V0.2 DEC 分析模块：ECTyper + pathotype 判断 + uidA 靶基因；(4) V0.2 Shigella 模块：ipaH 靶基因（替代 ShigEiFinder）；(5) Hermes 插件 13 tools 全部验证通过。
>
> **V0.1 → V0.2 关键变更**：(1) 放弃 HPC/SLURM 部署，改为个人 Linux 工作站/普通服务器；(2) 放弃 Nextflow，改用 Snakemake（Python DSL）；(3) 放弃 MongoDB + MinIO，改为 SQLite + 本地文件系统；(4) 明确 4 种目标病原与 V0.1 MVP 范围；(5) 引入三层 AI 防御机制应对公卫合规要求；(6) 引入"分层信任"理念区分固定 pipeline 与 AI 探索区。

---

## 一、项目背景

随着病原微生物全基因组测序（Whole Genome Sequencing，WGS）在疾病预防控制和科研中的广泛应用，生信分析已成为病原菌鉴定、耐药分析、毒力分析、分子分型及溯源分析的重要技术手段。

目前主流生信平台存在以下问题：

- 操作复杂，需要专业生信人员；
- 工作流固定，扩展性不足；
- 新分析工具接入成本高；
- 数据模型僵化，难以适应不同病原及分析流程；
- 缺乏 AI 自然语言交互能力；
- 缺乏统一的数据对象模型和知识管理能力。

本项目构建一个以 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 为核心、采用 Snakemake + MCP Plugin 扩展生信能力的 **AI Native 病原微生物基因组智能分析平台**，面向中小型疾控实验室。

### 1.1 切入点（V0.1 范围收敛）

为避免范围蔓延，V0.1 聚焦 **4 种食源性病原**：

| 病原 | 中文名 | 公卫意义 |
|---|---|---|
| *Salmonella* spp. | 沙门菌 | 最常见的食源性病原之一，分离量最大 |
| *E. coli* (DEC) | 致泻性大肠埃希菌 | STEC/EPEC/ETEC/EIEC/EAEC/DAEC 多 pathotype |
| *Shigella* spp. | 志贺菌 | 与 EIEC 高度同源，菌痢主因 |
| *Vibrio parahaemolyticus* | 副溶血性弧菌 | 海产品食物中毒主因 |

V0.1 先打通 **Salmonella 端到端**（最标准化、工具链最成熟），V0.2-V0.4 复用模式扩展至其余 3 种。

### 1.2 不做什么（V0.1 明确排除）

- ❌ 临床 IVD 合规路径（FDA 至今 0 个 LLM 病原检测产品 cleared，定位为 RUO/科研辅助）
- ❌ HPC/SLURM 集群部署
- ❌ 多租户/多机构云端 SaaS
- ❌ 实时暴发监测与自动预警（V2.0+）
- ❌ 70B+ 超大模型推理（V2.0+）

---

## 二、项目目标

### 2.1 核心能力（V0.1 必达）

1. **单样本端到端自动分析**：FASTQ 上传 → Snakemake 自动跑完 9 步标准 pipeline → 结果入 SQLite → PDF/HTML 报告
2. **自然语言交互**：用户用中文询问"分析这株沙门菌"、"和上次暴发株比较 SNP"、"生成耐药报告"等
3. **结果解读**：AI 解读 AMR/MLST/血清型结果，生成符合公卫规范的报告
4. **可追溯审计**：每个结论挂 (strain_id, pipeline_version, database_version) 三元证据链
5. **本地化部署**：单台 Linux 工作站/服务器即可运行，不依赖云

### 2.2 验收标准（V0.1）

| 指标 | 目标 |
|---|---|
| Salmonella 单样本端到端耗时（推荐档硬件） | ≤ 60 分钟 |
| 96 株/run 批处理耗时 | ≤ 8 小时 |
| 报告自动生成覆盖率（关键章节） | 100% |
| AI 解读错误率（经 deterministic verifier 拦截后） | ≤ 5% |
| 同一样本重跑结果差异 | 字段级完全一致（Immutable + Version） |
| Hermes Agent 会话中断后状态恢复 | 100%（基于 Snakemake `.snakemake/` + SQLite manifest） |

### 2.3 长期愿景（V2.0+）

- 多病原扩展（志贺菌以外的肠杆菌、霍乱弧菌、结核分枝杆菌等）
- 多 Agent 协作（暴发监测、自动预警、跨机构联网）
- 病原知识图谱（参考 [GPAS](https://www.medrxiv.org/content/10.64898/2026.02.18.26346517v1.full-text) 范式）
- RAG 文献检索与报告对比

---

## 三、总体架构

```
                User (公卫实验室操作员)
                
                          │  自然语言 / 命令行 / Web UI
                
                ┌─────────▼─────────┐
                │   Hermes Agent    │  ← NousResearch/hermes-agent (Python)
                │  (编排层/Orchestrator) │
                └─────────┬─────────┘
                          │  Skill 调用 / MCP tool 调用
                ┌─────────▼─────────┐
                │  Bioinformatics   │  ← SKILL.md + scripts/
                │     Skills        │
                └─────────┬─────────┘
                          │  subprocess: snakemake -s workflows/...
                ┌─────────▼─────────┐
                │ Snakemake Engine  │  ← Python DSL，基于 BacWORK fork
                │   (执行层)        │
                └─────────┬─────────┘
                          │  conda env / 容器化执行
                ┌─────────▼─────────┐
                │ Bioinformatics    │  ← pyrodigal/blast/bwa/iqtree/abricate/...
                │     Tools         │
                └─────────┬─────────┘
                          │  输出文件 + 元数据
                ┌─────────▼─────────┐
                │  Genome Object    │  ← Python 库 (本项目自研)
                │   Service (GOS)   │
                └─────────┬─────────┐
                          │           │
                ┌─────────▼──┐    ┌──▼──────────────┐
                │  SQLite    │    │ Local Filesystem │
                │ (元数据 +  │    │ data/{type}/     │
                │  JSON 列 + │    │   {id}/{ver}/    │
                │  FTS5 +    │    │   {file}         │
                │  sqlite-   │    │ + SHA256 索引    │
                │  vec)      │    │                  │
                └────────────┘    └──────────────────┘
```

### 3.1 分层信任（核心设计原则）

公卫场景的可重复性、可审计性要求与"AI 现场写代码"的灵活性存在根本张力。本项目采用**分层信任**架构：

| 层 | 信任度 | 内容 | AI 能做什么 |
|---|---|---|---|
| **L1 固定 pipeline** | 完全不信任 AI | 核心 9 步分析（QC/组装/物种/血清型/MLST/AMR/毒力/SNP/系统发育） | **只调用，不重写**；Snakemake rule 锁死，参数白名单 |
| **L2 受控探索** | AI 写代码 + sandbox + 人审 | 定制图表、跨样本比较、新发突变初探 | 写 Python/R 脚本，sandbox 跑过 + 用户 sign-off 才入报告 |
| **L3 自由对话** | AI 自由生成 | 用户问答、报告解读、文献摘要 | 受三层防御约束（schema + verifier + reflector） |

**业界证据**：业界唯一"AI 写生信代码"的 production 案例 [Helix.AI](https://github.com/Noricum-BioSoft/Helix.AI) 实际在数据密集型任务上**回到了 Nextflow + nf-core**（见 [`backend/nextflow_executor.py`](https://github.com/Noricum-BioSoft/Helix.AI/blob/main/backend/nextflow_executor.py)），仅 tabular 分析用 AI 写代码。本项目借鉴其 ExecutionBroker + Approve 门思想，但更严格——核心 pipeline 一律不允许 AI 改写。

### 3.2 关键技术选型一览

| 层 | V0.1 选型 | V1.0+ 迁移路径 |
|---|---|---|
| Agent 框架 | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | 无需迁移 |
| 工作流引擎 | **Snakemake v7.32.x**（锁定版本，v8 API 破坏性变更） | Snakemake v8+ |
| 元数据库 | **SQLite + WAL** + JSON 列 + FTS5 + [sqlite-vec](https://github.com/asg017/sqlite-vec) | PostgreSQL + pgvector |
| 大文件存储 | 本地文件系统 + SHA256 索引 | MinIO（共享存储场景） |
| 容器/环境 | **conda env**（首选）/ Singularity（可选） | 不变 |
| LLM 推理 | **Ollama** + 本地模型 | + vLLM（多用户场景） |
| 长任务状态 | **Snakemake `.snakemake/` 自带 resume** | 不变 |
| MCP server | Hermes 内置 MCP client + 自建病原 MCP | 不变 |
| KG（V0.3+） | SQLite + Apache AGE 扩展 | Neo4j |
| 向量库 | sqlite-vec（文献/报告模板） | pgvector |

---

## 四、设计理念

### 4.1 AI Native（保留）

- AI Agent 是整个系统唯一入口
- 所有操作均可通过自然语言完成

### 4.2 Plugin First（保留，扩展为三层）

- **Snakemake rule** = 执行层 plugin（最细粒度）
- **Skill** = 编排层 plugin（告诉 Agent 如何调用 Snakemake）
- **MCP server** = 服务层 plugin（暴露外部能力如查询 PubMLST、CARD）
- 平台本身不依赖具体分析软件
- 任何分析能力均可独立扩展

### 4.3 Document First（保留，落地为 SQLite + JSON）

所有业务对象采用 JSON Document 表示，存于 SQLite JSON 列。包括：

- Sample（样本）
- Workflow（工作流定义）
- Analysis（分析结果）
- Report（报告）
- Plugin（Snakemake rule + Skill 描述）
- Knowledge（KG 三元组）
- Task（异步任务）

### 4.4 Event First（保留）

系统保存完整分析过程，而不仅保存最终结果。Snakemake 自带详细 log，本项目额外在 SQLite 的 `events` 表中记录每次状态变化：

```
FASTQ Uploaded → QC Finished → Assembly Finished → Annotation Finished
→ AMR Finished → Report Generated
```

支持：审计、回放、Debug、AI 推理。

### 4.5 Version First（保留，强化为三元证据链）

所有对象必须记录版本：

- `schema_version`（GOM schema 版本）
- `pipeline_version`（Snakemake workflow Git SHA）
- `database_version`（AMR/MLST/血清型等参考数据库版本）
- `tool_versions`（shovill/gmlst/sistr/abricate 等工具版本）
- `prompt_version`（LLM prompt 模板版本）

**每个分析结论必须挂三元证据链**：`(strain_id, pipeline_version, database_version)`，监管复核时可追溯。

### 4.6 Immutable（保留）

分析结果不可覆盖，重新分析生成新的对象版本。SQLite 中通过 `(object_id, version)` 复合主键 + INSERT ONLY 约束实现。

### 4.7 分层信任（新增，见 §3.1）

公卫合规与 AI 灵活性的平衡——核心固定，边缘灵活。

---

## 五、Genome Object Model（GOM）

平台设计统一的数据对象规范。所有对象称为 **Genome Object（GO）**，采用 SQLite JSON 列存储。

### 5.1 标准 Schema（V0.1）

每个 GO 共有字段：

```json
{
  "object_id": "uuid-v4",
  "object_type": "sample | analysis | report | workflow | plugin | knowledge | task",
  "version": 1,
  "schema_version": "0.1.0",
  "created_at": "2026-06-27T10:00:00Z",
  "created_by": "user_id",
  "pipeline_version": "git-sha-of-snakemake-workflow",
  "database_versions": {
    "amrfinderplus_db": "2024-01-15.1",
    "card": "3.3.0",
    "pubmlst_schema": "2026-06-01"
  },
  "tool_versions": {
    "spades": "3.15.4",
    "sistr": "1.1.0",
    "bwa": "0.7.17", "iqtree": "3.1.2"
  },
  "payload": { }
}
```

### 5.2 Composite Triplet Schema（学 [GPAS](https://www.medrxiv.org/content/10.64898/2026.02.18.26346517v1.full-text) 论文）

AMR/MLST/毒力等结构化结果采用**复合三元组**模式防止近邻幻觉：

```json
{
  "gene": "blaCTX-M-15",
  "gene_attributes": {
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
  "drug": "Cefotaxime",
  "drug_attributes": {
    "class": "β-lactam/3rd-gen cephalosporin"
  }
}
```

**为什么用复合三元组**：`blaCTX-M-15` 与 `blaCTX-M-14`、`blaNDM-1` 在 embedding 空间高度接近。复合 schema 在结构层就区分（不同 mutation、不同 drug），让 deterministic verifier 能精确校验，避免向量化时近邻污染。

### 5.3 标准 Schema 与业界对齐

GOM 内部 JSON 可自定义，但 schema 必须可 1:1 映射到：

| 已有标准 | 用途 |
|---|---|
| [GA4GH](https://ga4gh.org/) | 基因组 API 与数据模型 |
| [BioSamples](https://www.ebi.ac.uk/biosamples/) (EBI) | 样本元数据 |
| [NCBI Pathogen Detection](https://www.ncbi.nlm.nih.gov/pathogens/) | 病原体检测数据模型 |
| [PulseNet cgMLST](https://www.cdc.gov/pulsenet/) | 分子分型命名 |
| [CARD/ARO Ontology](https://card.mcmaster.ca/) | AMR 本体 |

避免生态孤立、与公共数据库对接成本高。

### 5.4 SQLite 表结构（V0.1）

```sql
-- 核心对象表（所有 GO 共用）
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

-- FTS5 全文索引（关键文本字段）
CREATE VIRTUAL TABLE genome_objects_fts USING fts5(
  object_type, organism, strain_id, payload_text,
  content='genome_objects', content_rowid='rowid'
);

-- 事件流（Event First）
CREATE TABLE events (
  event_id TEXT PRIMARY KEY,
  object_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_payload TEXT NOT NULL,
  timestamp TEXT NOT NULL
);

-- 文件引用表（大文件不入 DB，只存引用）
CREATE TABLE file_artifacts (
  artifact_id TEXT PRIMARY KEY,
  object_id TEXT NOT NULL,
  file_type TEXT NOT NULL,
  file_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL
);

-- sqlite-vec 向量（V0.3+ 用于文献/报告模板）
-- CREATE VIRTUAL TABLE embeddings USING vec0(
--   object_id TEXT PRIMARY KEY,
--   embedding float[768]
-- );

-- 性能优化 PRAGMA
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA mmap_size = 30000000000;
PRAGMA wal_autocheckpoint = 1000;
PRAGMA temp_store = MEMORY;
```

---

## 六、数据架构

### 6.1 元数据存储：SQLite（V0.1）→ PostgreSQL（V1.0+）

**为什么 SQLite 起步**：

- 单文件、零运维、易备份（`sqlite3 .backup`）
- Hermes Agent 自己用 SQLite（[`~/.hermes/state.db`](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/session-storage.md)），技术栈一致
- NCBI [SRAdb](https://link.springer.com/article/10.1186/1471-2105-14-19) 数十年用 SQLite 分发 SRA 元数据，是生产先例
- 10M–100M 行舒适区，配合 WAL + FTS5 + [sqlite-vec](https://github.com/asg017/sqlite-vec) 可一站式解决元数据 + 全文 + 向量
- 已有 RAG 实战先例：[SRAKE](https://pkg.go.dev/github.com/nishad/srake)（SQLite + FTS5 + 向量 + MCP 服务于 SRA 元数据）

**迁移路径（V1.0+ 触发条件）**：

| 触发条件 | 迁移目标 |
|---|---|
| 并发用户 ≥ 5（SQLite WAL 单写瓶颈） | PostgreSQL |
| 元数据规模 > 1 亿行 | PostgreSQL |
| 需要复杂多表 JOIN（KG 推理） | PostgreSQL + Apache AGE（图扩展） |
| 需要更强向量检索（> 10M 向量） | PostgreSQL + pgvector |

迁移工具：`pgloader` 一键迁移；JSON 列直接对应 PostgreSQL `jsonb`。

### 6.2 大文件存储：本地文件系统 + SHA256 索引

```
data/
├── samples/
│   └── {strain_id}/
│       ├── fastq/
│       │   ├── {strain_id}_R1.fastq.gz
│       │   └── {strain_id}_R2.fastq.gz
│       └── assembly/
│           └── {strain_id}.fasta
├── analyses/
│   └── {analysis_id}/
│       └── v{version}/
│           ├── amr/
│           ├── mlst/
│           ├── snp/
│           └── report.pdf
└── cache/
    └── snakemake/
```

**每个文件入库 SQLite `file_artifacts` 表**（文件路径 + SHA256 + 大小），数据库本身不存大文件。

**V1.0+ 升级路径**：当多用户/多机共享需求出现时，迁移至 [MinIO](https://min.io/)（S3 兼容对象存储），SQLite 中文件路径改为 `s3://bucket/key` URI。

### 6.3 数据库版本化与备份

- **GOM schema 版本化**：每次 schema 变更 `schema_version` +1，旧 payload 永不删除（Immutable 原则）
- **参考数据库版本化**：CARD / VFDB / PlasmidFinder / PubMLST 等数据库每次更新记录版本号，分析结果挂对应版本
- **SQLite 备份策略**：
  - 每日 `sqlite3 db.sqlite ".backup 'db-YYYYMMDD.sqlite'"`
  - WAL checkpoint 后备份避免数据丢失
  - 备份文件上传至冷存储（HDD/NAS）

---

## 七、生信分析能力

### 7.1 核心 9 步标准 pipeline（L1 固定层）

| 步骤 | 工具 | 输入 | 输出 | V0.1 状态 |
|---|---|---|---|---|
| 1. 质控 | fastp | raw FASTQ | clean FASTQ + QC report | ✅ |
| 2. 组装 | Shovill (SPAdes-based, 含 read correction) | clean FASTQ | contigs FASTA | ✅ |
| 3. 物种鉴定 | **靶基因 BLAST 三物种分流**：invA(Salmonella) / uidA(E.coli/DEC) / ipaH(Shigella/EIEC) | contigs FASTA | 物种确认 | ✅ |
| 4. 注释 | pyrodigal + Prokka DBs（Python 原生，替代 Prokka CLI） | contigs FASTA | annotation JSON | ✅ |
| 5. MLST | gmlst (PubMLST salmonella_2) | contigs FASTA | ST 型 | ✅ |
| 6. AMR | abricate (CARD) | contigs FASTA | AMR 基因列表 | ✅ |
| 7. 毒力 | abricate (vfdb) | contigs FASTA | 毒力基因列表 | ✅ |
| 8. 质粒 | abricate (PlasmidFinder) | contigs FASTA | 质粒复制子 | ✅ |
| 9. SNP / 系统发育 | bwa + bcftools + iqtree（替代 snippy，避免 samtools 兼容性问题） | clean FASTQ + reference | VCF + tree | ✅ |
### 7.2 Snakemake 实现起点：fork BacWORK

V0.1 不从零写 Snakemake workflow。起点是 [FBi-ANSES/BacWORK](https://github.com/FBi-ANSES/BacWORK)（commit `5daf9b6`，2026-01 维护）——目前唯一一个 Snakemake-native、同时原生支持本项目 4 个目标病原（含 *V. parahaemolyticus*）的 pipeline。

**直接 fork 的模块**：

| 模块 | 来源 | 用途 |
|---|---|---|
| `workflow.smk` 整体骨架 | BacWORK | 4 病原统一入口、samplesheet 格式、`resume.json` 输出契约 |
| Mash 物种鉴定 rule | BacWORK | 物种分流前置 |
| Salmonella 模块（SISTR + gmlst） | BacWORK | Salmonella 血清型 |
| abricate rule | BacWORK | 4 病原通用 AMR |

**借鉴设计**：

| 设计 | 来源 | 借鉴价值 |
|---|---|---|
| Conditional serotyping | [davis-bc/SWAM-g](https://github.com/davis-bc/SWAM-g) | 按物种触发分型 rule（Mash 判物种后再跑专用 rule） |
| 资源约束 profile | [idolawoye/BAGEP](https://pmc.ncbi.nlm.nih.gov/articles/PMC7597632/) | 个人工作站 `--resources mem_mb` 配置；BAGEP 在 8 GB RAM 笔记本跑 20 株 Salmonella = 61 min 是直接对标基准 |

### 7.3 4 病原具体分析能力

#### 7.3.1 Salmonella（V0.1 已完成）

| 能力 | 工具 | Snakemake 集成 |
|---|---|---|
| 血清型 | SISTR | ✅ workflow 已验证 |
| MLST | gmlst (salmonella_2) | ✅ workflow 已验证 |
| AMR | abricate (CARD) | ✅ workflow 已验证 |
| 毒力 | abricate (vfdb) | ✅ workflow 已验证 |
| 质粒 | abricate (plasmidfinder) | ✅ workflow 已验证 |

#### 7.3.2 DEC（V0.2 — 规则文件已就位）

| 能力 | 工具 | Snakemake 集成 |
|---|---|---|
| 物种确认 | uidA 靶基因 BLAST | ✅ rule 已写 |
| 血清型（O:H） | ecoh_serotyper（Python 原生，委托 gene_scanner） | ✅ 已实现 |
| Pathotype | call_pathotype.py（stx1/stx2=STEC, eae=EPEC, ipaH=EIEC/Shigella, est/elt=ETEC, aggR=EAEC） | ✅ 脚本已写 |
| 毒力（stx/eae 等） | abricate (vfdb) | ✅ 通用 |
| AMR/质粒 | abricate (card/plasmidfinder) | ✅ 通用 |

#### 7.3.3 Shigella（V0.2 — 规则文件已就位）

| 能力 | 工具 | Snakemake 集成 |
|---|---|---|
| 物种确认/鉴别 | ipaH 靶基因 BLAST（替代 ShigEiFinder） | ✅ rule 已写 |
| 与 EIEC 鉴别 | ipaH 阳性 + shigella_serotyper 血清型 | ✅ 已实现 |
| AMR/毒力/质粒 | abricate（通用） | ✅ 通用 |

#### 7.3.4 Vibrio parahaemolyticus（V0.4，生态最薄弱，是机会点）

| 能力 | 工具 | Snakemake 集成 |
|---|---|---|
| O/K 血清型 | 自行开发中（不采用 Kaptive） | ✍️ **开发中** |
| 毒力（tdh/trh/tlh/toxR） | abricate 自定义库 | ✅ 已实现 |

**这是 Hermes-bacmap 的差异化价值点**——BacWORK 显式声明 *V. parahaemolyticus* "no specific steps"，本项目补全生态空白。

### 7.4 资源占用基准（个人工作站场景）

[SPAdes 官方 README](https://github.com/ablab/spades/blob/spades_3.15.4/README.md) + [BAGEP 实测](https://pmc.ncbi.nlm.nih.gov/articles/PMC7597632/)：

| 步骤 | 单株耗时（8-16 线程） | 峰值 RAM | 96 株/run 总耗时（推荐档 32 核/128 GB） |
|---|---|---|---|
| fastp（QC + trim） | 1-2 min | 1-2 GB | < 30 min |
| SPAdes（核心瓶颈） | 42 min（E. coli） | 8.4 GB | ~5-6 小时 |
| bwa+bcftools（SNP calling） | 4 min | 8-16 GB | ~1 小时 |
| abricate (CARD+VFDB+PlasmidFinder) | 3-4 min | < 4 GB | ~30 min |
| gmlst + SISTR + ecoh_serotyper | < 1 min | < 1 GB | < 10 min |

**关键瓶颈**：SPAdes 装配。**优化建议**：纯监测场景（不需 de novo）可跳过 SPAdes，仅用 bwa+bcftools 做 reference-based SNP calling，吞吐翻 3-5 倍。

---

## 八、AI Agent 能力与三层防御

### 8.1 Hermes Agent 职责

Hermes Agent 是系统唯一入口，负责：

- 自然语言理解（中英文）
- Workflow 选择（4 种病原各对应一个 Snakemake workflow）
- 参数填写（从样本元数据 + 用户指令构造 Snakemake config）
- 调用 Snakemake 执行（subprocess + log_handler 钩子）
- 监控执行状态（基于 Snakemake `.snakemake/` 状态 + log）
- 失败诊断与重试（解析 Snakemake log，识别 root cause）
- 结果入库（GOM 化 + SQLite）
- AI 解读与报告生成（L3 自由对话层）
- RAG 检索（V0.3+）

**Agent 不直接完成生信计算**，负责智能编排与解释。

### 8.2 三层防御机制（公卫合规必备）

**业界证据**：[BixBench](https://arxiv.org/pdf/2503.00096) 实测 Claude 3.5 Sonnet 在生信任务仅 17% 准确率；[Globus HPC 论文](https://arxiv.org/abs/2508.18489) §6.3 承认 agents "made repetitive mistakes... would not always complete outlined tasks"。**LLM 在临床场景的幻觉不可接受**，必须有强制防御。

```
LLM 生成（JSON schema constrained decoding）
    ↓
Layer 1: Schema 校验
  - 输出必须符合 GOM JSON Schema
  - 字段类型、必填项、枚举值校验
  - 失败 → 重生成（最多 3 次）
    ↓
Layer 2: Deterministic Verifier（确定性规则校验）
  - AMR 基因必须在 CARD 数据库（exact match）
  - MLST ST 必须在 PubMLST schema
  - 血清型必须符合 Kauffmann-White（Salmonella）/ 相应命名法
  - SNP cluster allele 差距阈值（参考 PulseNet cgMLST ≤10 allele）
  - 引用 PMID 必须存在（PubMed API cross-check）
  - 失败 → 拒绝结论，标记 NEEDS_HUMAN_REVIEW
    ↓
Layer 3: NLI Reflector（CRAG 模式，自然语言推理校验）
  - 把 LLM 输出分解为 atomic claims
  - 每条 claim 与检索上下文比对（entailment/contradiction）
  - 参考 Self-Correcting RAG AP 0.85 目标
  - contradiction rate > 阈值 → 触发人审
    ↓
Evidence-linked Report
（每条结论挂 (strain_id, pipeline_version, database_version) 三元证据链）
```

### 8.3 RAG 架构（V0.3+，三层存储）

**核心原则**：**菌株分析结果（结构化事实）不入向量库**，避免近邻幻觉（`blaCTX-M-15` ↔ `blaCTX-M-14`）。

| 层 | 存什么 | 检索方式 | 单一职责 |
|---|---|---|---|
| **Source of Truth** | 菌株分析结果（AMR 基因、MLST ST、血清型、SNP cluster） | SQL 精确查询 | 事实查询，零幻觉 |
| **知识图谱（KG）** | AMR 基因-药物-机制、MLST ST-克隆群、毒力-疾病、SNP 聚类拓扑 | Cypher（Apache AGE） | 推理型查询 |
| **向量库（sqlite-vec）** | 文献全文 chunk、报告模板、自然语言注解 | hybrid（BM25 + dense） | 语义召回 |

**最强证据**：[Ontology-grounded GraphRAG](https://www.sciencedirect.com/science/article/abs/pii/S1532046426000171) 实测，准确率从通用 LLM 的 37% 提到 98%，幻觉率从 ~63% 降到 1.7%。

### 8.4 Hermes 在长任务场景的使用模式

**关键约束**（来自 Hermes 源码核查）：

- Hermes 的 `process_registry` **最多 64 并发跟踪进程**，**完成态记录保留 30 分钟后清除**（[`tools/process_registry.py`](https://github.com/NousResearch/hermes-agent/blob/main/tools/process_registry.py)）
- **subagent 不能跨 session 持久化**（[`tools/delegate_tool.py:2553`](https://github.com/NousResearch/hermes-agent/blob/main/tools/delegate_tool.py) 原话："there is no persistent channel"）
- 因此**长任务必须由 Snakemake 管理**，Hermes 仅负责调用与解读

**正确姿势**：

```python
from snakemake import snakemake

snakemake(
    snakefile="workflows/salmonella/Snakefile",
    config={
        "samples": "config/samples.tsv",
        "reference": "refs/Salmonella_LT2.fa",
    },
    cores=16,
    workdir=f"work/{strain_id}",
    use_conda=True,
    log_handler=hermes_log_handler,
)
```

**Snakemake 的 `.snakemake/` 目录自带完整状态**：DAG、已完成步骤、checkpoint、conda env 锁定。**会话中断后 Hermes 直接重启 snakemake 命令即可自动 resume**，无需自建 jobs.json。

---

## 九、LLM 推理方案

### 9.1 选型

| 版本 | 推荐模型 | 显存占用（Q4_K_XL） | 速度（RTX 5090, 4K ctx） | 适用 |
|---|---|---|---|---|
| **V0.1** | **Qwen3-14B** | ~8.5 GB | ~124 tok/s | 单用户，Hermes + tool calling |
| V0.5 | Qwen3-32B（dense） | ~18.6 GB | ~61 tok/s | 提升解读质量 |
| V1.0 | Qwen 3.6 27B/35B | ~16-20 GB | ~80-100 tok/s | [NVIDIA × Hermes 联合推荐](https://blogs.nvidia.com/blog/rtx-ai-garage-hermes-agent-dgx-spark/) |
| V2.0+ | 70B（双卡） | ~43 GB | ~25-35 tok/s | 多用户/复杂推理 |

**为什么 Qwen3-14B 起步**：

- 量化后 ~8.5 GB 显存，RTX 4090/5090 都有 15+ GB headroom
- 5090 上 ~124 tok/s，4090 上 ~80 tok/s，足以支撑多步 tool calling
- 64K 上下文满足 Hermes Agent 硬性要求（[providers 文档](https://hermes-agent.nousresearch.com/docs/integrations/providers)）
- 中英双语能力强（公卫场景多为中文）

### 9.2 推理引擎：API-key 模式（V0.1）

[2026 多家 benchmark](https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/) 一致结论：**单用户场景 Ollama / llama.cpp / vLLM 差距 < 15%**。vLLM 仅在 ≥10 并发用户时有 10× 优势。

**V0.1 采用 API-key 模式**（外部 LLM 服务，不安装本地推理引擎）：

- Hermes Agent 原生支持任意 OpenAI-compatible API
- 配置：环境变量 `OPENAI_API_KEY`（或对应服务商 key）+ Hermes config 指定 model 和 endpoint
- 兼容服务商：智谱 GLM / Kimi / OpenAI / Anthropic / 任意 OpenAI-compatible 端点
- 优势：无需 GPU、无需下载模型、部署简单
- 数据合规：仅发送分析结果摘要（不发送原始 FASTQ/基因组），每次调用审计日志

**V1.0+ 可选迁移至本地推理**（Ollama / vLLM），当多用户场景或数据出境合规要求时启用。

### 9.3 CPU 兜底（仅 dev/CI）

无 GPU 环境可用 llama.cpp + AVX-512 跑 Qwen3-8B Q4_K_M：

- AMD Ryzen 9 9950X ~15 tok/s（[llama.cpp PR #12773](https://github.com/ggml-org/llama.cpp/pull/12773)）
- AMD Threadripper PRO 7995WX ~17 tok/s（[justine.lol/matmul](https://justine.lol/matmul/)）

**仅用于流程验证，生产不可接受**（Hermes 多步 tool calling 每步 prompt eval 10-30 秒，0.3 秒/token 体验差）。

### 9.4 外部 API 选项（可选）

公卫数据合规优先本地推理。若实验室允许，可配置外部 API（OpenAI / Anthropic / 智谱 / Kimi）：

- 每次外部调用必须审计日志
- 默认 OFF，需管理员显式启用
- 不发送原始 FASTQ/基因组数据，仅发送分析结果摘要

---

## 十、运行环境与部署

### 10.1 部署目标

**个人 Linux 工作站或普通服务器**（非 HPC）。单机或小型 SMP 服务器，无 SLURM 调度，无 root daemon 依赖。

### 10.2 三档硬件配置

| 维度 | 🥉 最低（能跑通） | 🥈 推荐（96 株/run + Qwen3-14B） | 🥇 舒适（多用户 + Qwen3-32B） |
|---|---|---|---|
| **CPU** | AMD Ryzen 9 9950X (16c/32t) | **AMD Threadripper 7960X (24c/48t)** | AMD Threadripper PRO 7985WX (64c/128t) |
| **RAM** | 64 GB DDR5-6000 | **128 GB DDR5-5200 RDIMM (4 通道)** | 256 GB DDR5-5200 ECC RDIMM (8 通道) |
| **GPU** | RTX 4090 24 GB | **RTX 5090 32 GB** | 2× RTX 5090 32 GB 或 RTX PRO 6000 96 GB |
| **主 NVMe** | 2 TB PCIe 4.0 | **4 TB PCIe 5.0** | 8 TB PCIe 5.0 RAID 1 |
| **副 NVMe**（LLM + SQLite） | 1 TB PCIe 4.0 | 2 TB PCIe 4.0 | 4 TB PCIe 5.0 |
| **冷存储 HDD** | 8 TB | 2× 16 TB RAID 1 | 4× 20 TB RAID 10 或 TrueNAS |
| **网络** | 千兆 | 2.5 GbE + WiFi 7 | 10 GbE + WiFi 7 |
| **电源** | 850 W Gold | 1200 W Platinum | 1600 W Titanium |
| **估算成本** | ~$3,500 / ¥28k-32k | **~$8,500-10,000 / ¥70k-85k** | ~$20,000-25,000 / ¥160k-210k |

### 10.3 关键约束

1. **CPU**：AMD Zen4 Threadripper（PRO 优先）；避免非 PRO 7980X（4 通道内存瓶颈）。详见 [Puget Systems 测试](https://www.pugetsystems.com/labs/hpc/amd-zen4-threadripper-pro-vs-intel-xeon-w9-for-science-and-engineering/)
2. **GPU**：单用户首选 RTX 5090 32 GB；70B+ 需双卡（PCIe bottleneck 效率 0.70×）
3. **存储**：**NVMe 是底线**——Snakemake 一个 run 产生几十万小文件，SATA SSD 都会成为瓶颈；数据盘/模型盘/SQLite 盘建议分离
4. **避免**：H100/A100（单用户严重浪费）、Mac Studio（生信 ARM 工具链参差）、Intel Xeon W9（同价位输给 TrPRO）

### 10.4 软件栈

| 组件 | 版本 | 安装方式 |
|---|---|---|
| OS | Ubuntu 22.04 LTS / 24.04 LTS | - |
| Python | 3.11 | uv（[README 已配置](README.md)） |
| Hermes Agent | 最新 main 分支 | [官方文档](https://hermes-agent.nousresearch.com/docs/) |
| Snakemake | **v7.32.x**（锁定，v8 API 破坏性） | conda/mamba |
| 生信工具 | 见 §7 | pixi（[README 已配置](README.md)） |
| SQLite | 3.40+（含 FTS5） | 系统自带 |
| sqlite-vec | 最新 | SQLite 扩展 |
| Ollama | 最新 | [官方脚本](https://ollama.com/) |

### 10.5 多用户场景（V1.0+）

V0.1 默认单用户。V1.0+ 引入：

- 每用户独立 Hermes 实例（systemd user service）
- 共享 Snakemake 工作目录隔离（per-user `work/`）
- 共享 SQLite 数据库 + 行级权限（`created_by` 字段）
- 审计日志强制

---

## 十一、长任务管理与恢复

### 11.1 短任务 vs 长任务划分

| 类型 | 典型耗时 | 处理方式 |
|---|---|---|
| 短任务（查询、解析、生成报告） | < 5 min | Hermes 同步调用 + 即时返回 |
| 中等任务（单株 mlst/abricate） | 5-30 min | Hermes 后台调用 + 轮询完成 |
| **长任务（96 株 batch、SPAdes 装配）** | 30 min - 数小时 | **Snakemake 主导 + Hermes 解耦** |

### 11.2 长任务架构（关键设计）

```
1. Hermes Agent 调用 Skill
2. Skill 通过 Python API 调用 snakemake()，立即触发
3. Snakemake 在子进程跑：
   - 自带 DAG 编排
   - 自带 --rerun-incomplete 恢复
   - 自带 --cores / --resources 资源限制
   - .snakemake/ 目录持久化所有状态
4. log_handler 钩子把进度反馈给 Hermes（可选）
5. 完成后 Snakemake 返回 → Hermes 入库 + 通知用户
6. 若中途 Hermes 会话断开：
   - Snakemake 子进程继续跑（独立进程）
   - 或被中断（kill 信号）
   - 用户重启 Hermes 后再次调用 snakemake() → 自动 resume
```

### 11.3 Snakemake 自带恢复机制（不需要自建 jobs.json）

| 机制 | 作用 |
|---|---|
| `.snakemake/` 目录 | 持久化 DAG、已完成步骤、conda env 锁定 |
| `--rerun-incomplete` | 不完整的输出文件自动重跑 |
| `--keep-going` | 单步失败时继续其他分支 |
| `--resources mem_mb=N` | 资源调度避免 OOM |
| `--restart-times 3` | 单 rule 失败自动重试 |

**禁止**：让 Hermes 进程内 `while sleep; squeue` 轮询（个人电脑场景无 SLURM，且 Hermes 进程死亡会丢失上下文）。

### 11.4 失败诊断（✅ 已实现 V0.5）

Snakemake 失败时 `failure_diagnostics.py` 自动解析 log，识别 9 种错误模式并给出修复建议：

- Lock 冲突 → `snakemake --unlock`
- OOM → 减少线程或内存限制
- 工具版本不兼容 → 更新 pixi 环境
- 参考数据库缺失 → 重建 BLAST 索引
- 测序数据质量差 → 提示重新测序
- 磁盘空间不足 → 清理临时文件
- 权限问题 → 检查文件权限
- Snakemake v8 不兼容 → 锁定 7.32.x
- 超时 → 检查僵尸进程

集成到 `run_analysis.py` 失败路径 + `bio_diagnose` Hermes tool（第 18 个 tool）。

---

---

## 十二、开发质量保证

公卫场景下，**质量保证是硬需求**，不是可选项。结果影响公卫决策、监管审计要求可验证性、AI 生成内容需独立验证。本章定义贯穿开发全过程的质量保证机制。

### 12.1 测试金字塔

| 层级 | 范围 | 工具 | 覆盖率要求 |
|---|---|---|---|
| **单元测试** | GOM、Deterministic Verifier、Composite Triplet Schema、Snakemake config 构造、文件 SHA256、路径管理 | pytest + pytest-cov | **核心库 ≥ 90%** |
| **集成测试** | Snakemake workflow + Hermes Skill（小样本 1-2 株）；SQLite 入库正确性；`.snakemake/` 恢复 | pytest + tmp fixtures | 工具调用层 ≥ 80% |
| **E2E 测试** | 自然语言指令 → 完整分析 → 报告生成；状态恢复（kill + restart） | pytest + subprocess | 应用层 ≥ 60% |
| **回归测试** | 同一样本重跑字段一致性；DB 迁移；工具升级；DB 更新 | pytest-snapshot + cron | 关键路径 100% |

**工具链**：pytest + pytest-cov + coverage.py + [Codecov](https://about.codecov.io/)（开源免费）。

### 12.2 TDD 与测试策略（核心库 TDD，应用层测试覆盖）

#### 核心库强制 TDD（red-green-refactor）

以下核心库**必须 TDD**——先写测试再写实现：

| 核心库 | 理由 |
|---|---|
| **Genome Object Service (GOS)** | 数据模型基础，错一处扩散全网 |
| **Deterministic Verifier** | 公卫合规关键，AMR/MLST/血清型校验不能错 |
| **Composite Triplet Schema** | 防幻觉的结构层，schema 错则 verifier 失效 |
| **Snakemake config 构造器** | 错误 config 导致整个 workflow 错跑 |
| **文件 SHA256 + 路径管理** | 数据完整性基础 |

#### 应用层测试覆盖（写完代码补测试）

| 应用层 | 策略 |
|---|---|
| Hermes Skill（analyze_salmonella 等） | 集成测试为主，mock LLM 响应 |
| 报告生成（PDF/HTML） | snapshot testing |
| LLM 解读 | 对比金标准 + 人工审核 |
| Web UI（V0.4+） | Playwright E2E |

### 12.3 分析验证（Analytical Validation，公卫特有）

公卫基因组分析的**方法学验证**是 ISO 15189 / CAP 等合规体系的硬要求。本项目用 Gold standard 样本集做验证：

#### Gold Standard 样本集（V0.1 Sprint 0 准备）

- **≥ 50 株已鉴定样本**（ATCC 参考株 + CDC/NCBI 公开已鉴定分离株）
- 涵盖 4 种目标病原，每种 ≥ 10 株
- 含已知 AMR 谱、MLST ST、血清型、毒力基因（来自传统方法或权威数据库）

#### 验证指标（每 release 更新）

| 指标 | 目标 | 对比基线 |
|---|---|---|
| AMR 检测灵敏度 | ≥ 95% | vs gold standard 验证集(https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7665300/) |
| AMR 检测特异性 | ≥ 98% | 同上 |
| MLST ST 准确率 | ≥ 99% | vs [PubMLST](https://pubmlst.org/) |
| 血清型预测准确率 | ≥ 95% | vs 传统血清学 + [EnteroBase](https://enterobase.warwick.ac.uk/) |
| 物种鉴定准确率 | ≥ 99% | vs [NCBI Taxonomy](https://www.ncbi.nlm.nih.gov/Taxonomy/) |

#### 与成熟平台对比基准

每 release 跑同一批 Gold standard 样本到：
- [Bactopia](https://github.com/bactopia/bactopia)（业界事实标准）
- [Enterobase](https://enterobase.warwick.ac.uk/)（公卫先例）
- [SnapperDB](https://github.com/ukhsa-collaboration/snapperdb)（PHE 内部 SNP 监测）

差异 > 5% 必须有解释（数据库版本、工具参数、参考基因组差异等）。

### 12.4 回归测试（关键）

| 测试 | 频率 | 工具 | 通过标准 |
|---|---|---|---|
| **同一样本重跑字段级一致性** | 每次 commit + 每周 cron | pytest-snapshot | 100% 字段一致（Immutable 强制） |
| **数据库迁移测试** | 每次 release | SQLite → PostgreSQL 模拟（pgloader） | 字段一致 + 性能不退化 > 10% |
| **工具升级回归** | shovill/gmlst/sistr/abricate 升级时 | gold standard 套件 | AMR/MLST/血清型结果差异 < 1% |
| **参考数据库更新** | AMR/CARD/PubMLST 更新时 | gold standard 套件 | 已知 AMR 基因 100% 检出，新基因加入版本注记 |
| **Snapshot 测试（报告生成）** | 每次 PR | pytest-snapshot | 报告字段一致（允许时间戳差异） |

### 12.5 AI 输出验证

**业界警示**：[BixBench](https://arxiv.org/pdf/2503.00096) 实测 Claude 3.5 Sonnet 生信任务仅 17% 准确率。AI 输出必须有独立验证。

| 验证 | 频率 | 工具 | 通过标准 |
|---|---|---|---|
| **金标准对比集（≥ 200 案例，人工标注）** | 每次 release | 人工 + 自动 | 关键结论一致率 ≥ 95% |
| **Hallucination rate 监控** | 每次 release + 每月 cron | LLM-as-Judge + 人工抽样 | ≤ 5%（目标 ≤ 2%） |
| **Verifier 拦截率监控** | 实时 | Prometheus | 异常升高（> 20%）触发告警，说明 LLM 退步 |
| **模型版本升级回归** | Qwen3-14B → 32B 等 | 金标准 + AMR/MLST 套件 | 关键结论一致率不下降 |
| **Prompt A/B 测试** | 新 prompt 上线前 | 100 case A/B | 新版本不退化才能合并 |

### 12.6 工程实践

| 实践 | 要求 |
|---|---|
| **Code Review** | 所有 PR 必须有 ≥ 1 个 reviewer +1；核心库（GOS/Verifier）需 ≥ 2 人 |
| **类型注解** | 100%（mypy strict 模式） |
| **Pre-commit hooks** | ruff（lint + format）+ mypy + markdownlint + JSON Schema validation + 私密扫描（git-secrets） |
| **分支策略** | trunk-based；feature branch + squash merge；main 始终可发布 |
| **CHANGELOG** | 每个 PR 必须更新 [CHANGELOG.md](https://keepachangelog.com/) |
| **架构决策记录（ADR）** | 重要决策写 [ADR](https://adr.github.io/)，存 `docs/adr/` |
| **API 文档** | Sphinx + autodoc 自动生成，每 release 发布 |

### 12.7 CI/CD（GitHub Actions）

#### 每次 Pull Request 自动

```yaml
# .github/workflows/ci.yml 触发：pull_request
jobs:
  - lint: ruff check + ruff format --check
  - typecheck: mypy --strict
  - unit-tests: pytest tests/unit/ + 覆盖率上传 Codecov
  - integration-tests: pytest tests/integration/ (small sample)
  - schema-validation: pydantic schema check for all GOM examples
  - security-scan: pip-audit + Trivy（容器扫描）
  - changelog-check: CHANGELOG.md 必须更新
  - docs-build: Sphinx 构建检查
  - coverage-gate: 覆盖率不能比 main 下降超过 2%
```

#### 每次 merge to main 自动

```yaml
# .github/workflows/main.yml
jobs:
  - regression-tests: 完整回归测试套件（含 gold standard）
  - build-artifacts: conda env lock + Docker/Singularity 镜像
  - deploy-staging: 自动部署 staging（V0.4+）
```

#### 发布流程（tag 触发）

```yaml
# .github/workflows/release.yml 触发：v*.*.* tag
jobs:
  - full-analytical-validation: 完整 gold standard 套件 + 平台对比
  - generate-sbom: SBOM（软件物料清单）生成
  - github-release: 自动从 CHANGELOG 生成 release notes
  - publish-artifacts: 上传到 GitHub Releases + 容器 registry
```

### 12.8 数据完整性

| 校验 | 频率 | 实现 |
|---|---|---|
| **GOM JSON Schema 强制** | 每次写入 | pydantic 模型，运行时校验 |
| **文件 SHA256 校验** | 每周 cron | 比对 `file_artifacts.sha256` 与实际文件 |
| **SQLite 外键约束** | 持续 | `PRAGMA foreign_keys = ON` |
| **事务边界** | 每次写 | 显式 `BEGIN/COMMIT`，避免部分写入 |
| **元数据 vs 文件系统对账** | 每周 cron | 找出"孤儿文件"（FS 有但 DB 无）或"无文件元数据"（DB 有但 FS 无） |
| **数据库备份完整性** | 每月 | restore 测试，验证可恢复 |

### 12.9 性能基准

| 维度 | 指标 | 频率 | 通过标准 |
|---|---|---|---|
| **单样本端到端** | 三档硬件各测一次 | 每 release | 不退化 > 10% |
| **96 株 batch** | 推荐档硬件 | 每 release | 不退化 > 10% |
| **LLM 推理速度** | tok/s（单 prompt） | 每周 cron | 不低于基线 80% |
| **SQLite 查询性能** | 1M / 10M / 100M 行 | 每 release | p95 < 100ms |
| **资源使用率** | CPU/RAM/GPU/磁盘 IO | 实时监控（V0.4+） | Prometheus + Grafana 告警 |

### 12.10 安全测试

| 测试 | 频率 | 工具 |
|---|---|---|
| **Python 依赖扫描** | 每次 PR + 每日 cron | [pip-audit](https://github.com/pypa/pip-audit) + [Dependabot](https://docs.github.com/en/code-security/dependabot) |
| **Conda/Bioconda 依赖扫描** | 每周 | pixi audit + 手工审查 |
| **容器镜像扫描** | 每次构建 | [Trivy](https://github.com/aquasecurity/trivy) |
| **SBOM（软件物料清单）** | 每 release | [syft](https://github.com/anchore/syft) + 上传 GitHub Releases |
| **密钥扫描** | 每次 commit | pre-commit + [git-secrets](https://github.com/awslabs/git-secrets) |
| **输入验证** | 持续 | 所有用户输入走 JSON Schema 校验 |
| **速率限制** | 持续 | Hermes Agent tool call rate limit（防 token 滥用） |
| **权限边界** | 持续 | 文件 ACL：Hermes 进程对样本目录只读、output 读写、系统零权限（见 §14.2） |

### 12.11 可访问性测试（V0.4+ Web UI）

V0.4 引入 Web UI 后必须满足：

| 标准 | 工具 |
|---|---|
| [WCAG 2.1 AA](https://www.w3.org/TR/WCAG21/) 合规 | [axe-core](https://github.com/dequelabs/axe-core) 自动扫描（CI 集成） |
| 键盘导航 | 手工 + Playwright 自动化 |
| 屏幕阅读器兼容 | [NVDA](https://www.nvaccess.org/) / VoiceOver 手工测试 |
| 颜色对比度 | [WCAG Color Contrast Checker](https://chrome.google.com/webstore/detail/wcag-color-contrast-check/) |
| 响应式设计 | Playwright 多 viewport 测试 |

### 12.12 文档与可追溯

| 文档 | 频率 | 工具 |
|---|---|---|
| **架构决策记录（ADR）** | 重要决策时 | [adr-tools](https://github.com/npryce/adr-tools)，存 `docs/adr/` |
| **CHANGELOG.md** | 每个 PR 必须更新 | [Keep a Changelog](https://keepachangelog.com/) 格式 |
| **API 文档** | 自动生成 | Sphinx + autodoc，每 release 发布 |
| **测试用例与需求双向追踪矩阵** | 每 release | `docs/traceability-matrix.md`，每个验收项 ↔ 测试 case ID |
| **Runbook（运维手册）** | 每 release | `docs/runbook/`，含常见故障与恢复流程 |

---

## 十三、开发路线


### 13.1 阶段切分（V0.1 → V1.0）

```
┌─────────────────────────────────────────────────────────────────┐
│ V0.1 (MVP) — ✅ 完成                                              │
│ Salmonella 端到端：Hermes + Snakemake + SQLite + GLM-5.2        │
│ 6 株 Gold standard + 13 tools + 87 tests + HTML 报告            │
└─────────────────────────────────────────────────────────────────┘
│ 验收：96 株 ≤ 8h，AI 解读 + 报告                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ V0.2 — ✅ 完成                                                     │
│ 扩展 DEC（ecoh_serotyper + uidA + pathotype）+ Shigella（ipaH）— 10 株验证通过
│ + Snippy SNP + iqtree 系统发育                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ V0.3 (计划)                                                       │
│ Snippy SNP + iqtree 系统发育                                      │
│ + KG 引入（Apache AGE）+ 三层防御完善                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ V0.4 (计划)                                                       │
│ V. parahaemolyticus + RAG + 暴发聚类可视化                       │
│ + 多用户支持（V1.0 准备）                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ V1.0 (计划)                                                       │
│ PostgreSQL 迁移 + 多用户 + 部署文档                               │
└─────────────────────────────────────────────────────────────────┘
```

### 13.2 V0.1 详细任务（Salmonella MVP）— ✅ 全部完成

#### Sprint 0（第 0 周）：质量基础设施 + Gold standard — ✅

- [x] GitHub Actions CI pipeline + pre-commit hooks + pytest 框架
- [x] GenomeObjectService TDD 测试套件（61 tests）
- [x] Gold standard 样本集（6 Sal + 1 E. coli，FASTQ 下载 MD5 校验）
- [x] Deterministic Verifier TDD 测试套件（21 tests）

#### Sprint 1（第 1-3 周）：基础设施 — ✅

- [x] Snakemake Salmonella workflow（62 job DAG）
- [x] GenomeObjectService 完整实现（SQLite + CRUD + 版本 + 事件）
- [x] invA 物种验证（bwa + blastn 双层，灵敏度+特异性 100%）
- [x] Hermes Skill analyze-salmonella + 编排脚本 run_analysis.py

#### Sprint 2（第 4-6 周）：Snakemake 集成 — ✅

- [x] 6 株端到端批量跑 + GOM 入库（智能去重 + 版本管理）
- [x] Hermes 插件部署 + API-key 模式 LLM（GLM-5.2 via Z.AI）

#### Sprint 3（第 7-9 周）：AI 解读与报告 — ✅

- [x] Deterministic Verifier 实现（21 tests，6 株真实验证全通过）
- [x] HTML 报告生成（含 Verifier + 三元证据链）
- [x] Hermes 插件 13 tools（8 底层 + 5 高层）+ 端到端自然语言交互验证

### 13.2.1 V0.2 DEC + Shigella 扩展 — ✅ 完成

- [x] ipaH 参考基因获取 + BLAST DB + bwa index（Shigella/EIEC 靶基因，1827 bp）
- [x] uidA 参考基因获取 + BLAST DB + bwa index（E. coli/DEC 靶基因，1190 bp）
- [x] 三物种靶基因特异性验证矩阵（invA/uidA/ipaH 交叉验证全通过）
- [x] ECTyper 安装 + Snakemake rule（dec_ectyper）
- [x] call_pathotype.py（STEC/EPEC/EIEC/ETEC/EAEC 基因组合判断）
- [x] ipaH BLAST rule（dec_ipaH_blast，替代 ShigEiFinder）
- [x] report.smk 更新（新增 DEC 字段：ectyper/pathotype/ipaH）
- [x] Snakefile include dec_shigella.smk + DAG 验证（25 new jobs）
- [ ] DEC/Shigella Gold standard 样本下载 + 端到端测试
- [ ] V0.2 release

### 13.3 V0.1 验收清单

| 项 | 验收标准 |
|---|---|
| Salmonella 单株端到端 | 5 株测试样本全部通过 9 步分析 + 报告 |
| 96 株 batch | ≤ 8 小时完成（推荐档硬件） |
| AI 解读 | 关键字段（血清型/ST/AMR/毒力）deterministic verifier 通过率 ≥ 95% |
| 重跑一致性 | 同一样本重跑字段级完全一致 |
| 状态恢复 | kill Hermes + Snakemake 后，重启能 resume |
| 报告生成 | 自动生成 PDF + HTML，含三元证据链 |
| 自然语言交互 | "分析这株沙门菌" → 触发完整流程 |
| **CI 流水线** | PR 触发 lint/typecheck/unit-tests/coverage gate 全绿；覆盖率不下降 > 2% |
| **Gold standard 验证** | ≥ 10 株 Salmonella 在 AMR/MLST/血清型上 vs EnteroBase/Bactopia 一致率 ≥ 95% |
| **核心库 TDD** | GOS/Verifier/Triplet schema/Config builder 覆盖率 ≥ 90%，所有测试 TDD 起源 |
| **AI 金标准** | ≥ 50 case 对比集，关键结论一致率 ≥ 90%（V1.0 目标 ≥ 95%） |
| **CHANGELOG + ADR** | 每个 Sprint 至少 1 条 CHANGELOG 条目，关键决策有 ADR |

---

## 十四、风险登记册与护栏

### 14.1 风险排序

| # | 风险 | 等级 | Mitigation |
|---|---|---|---|
| 1 | **核心 pipeline 让 AI 写代码** → 监管/审计失败 | Critical | 分层信任（§3.1）：核心 9 步锁死，AI 不重写 |
| 2 | **AMR/MLST/血清型幻觉**（如 blaCTX-M-15 → blaNDM-1） | High | 三层防御（§8.2）：Schema + Verifier + Reflector |
| 3 | **菌株结果向量化的近邻污染** | High | 不入向量库（§8.3），用 SQL 精确查询 + KG 推理 |
| 4 | **参考数据库版本失控**（AMR/MLST DB 持续更新） | High | Version First 强制 + 三元证据链 |
| 5 | **Snakemake v8 API 破坏性变更** | Medium | 锁定 v7.32.x，迁移前充分测试 |
| 6 | **本地 LLM 推理速度不够**（CPU 兜底场景） | Medium | 强制 GPU 部署；CPU 仅 dev/CI |
| 7 | **数据库迁移（SQLite → PostgreSQL）破坏数据** | Medium | V1.0 用 pgloader 充分测试；V0.1 schema 兼容 PG jsonb |
| 8 | **公卫数据外流**（外部 API 误用） | Medium | 默认本地推理；外部 API 需管理员显式启用 + 审计 |
| 9 | **V. parahaemolyticus 工具链空白** | Medium | V0.4 重点补全，是差异化价值点 |
| 10 | **Hermes Agent 上游变更** | Low | fork + 锁版本；定期 sync main |

### 14.2 护栏机制（必备）

1. **工具调用白名单 + JSON schema 强校验**：未注册 Snakemake rule 一律拒绝
2. **文件系统 ACL**：Hermes 进程对样本目录只读、output 读写、系统零权限
3. **AI 生成代码强制 sandbox 执行**（临时目录）+ 人审 sign-off 才入报告
4. **per-session 预算三重封顶**：token + 墙钟时间 + Snakemake core-hours
5. **强制 dry-run + 人审 sign-off**：报告出系统前必须人工勾选
6. **全量审计日志**：每次 Snakemake 调用 / LLM prompt / tool call 入库（who/when/what/prompt/output），可追溯单一样本全部分析历史
7. **LLM 输出确定性回放**：固定 seed + 缓存 prompt→output，便于事后复现

---

## 十五、项目愿景

Hermes-bacmap 不仅是一个生信分析平台，而是一个 **AI Native 病原微生物基因组智能平台**。

平台以 **Hermes Agent** 为智能核心，以 **Genome Object Model（GOM）** 为统一数据标准，以 **Snakemake Workflow** 为可扩展的生信执行层，以 **SQLite + 本地文件系统** 为轻量数据基础设施，实现病原微生物基因组分析、知识管理、智能推理和溯源分析的一体化。

最终目标是打造一个**开放、可扩展、可持续演进的生信智能体生态**，为临床、疾控和科研提供统一的 AI 生信分析能力。

---

## 附录 A：核心创新点（V0.2 强化）

### A.1 Genome Object Model（GOM）

定义所有数据对象的统一规范、生命周期和事件模型，使平台不依赖具体数据库实现。

**V0.2 强化**：

- 基于 SQLite + JSON 列，单文件可移植
- Composite Triplet Schema（学 GPAS）防止结构化数据幻觉
- 三元证据链 `(strain_id, pipeline_version, database_version)` 强制可追溯
- schema 与 GA4GH / BioSamples / NCBI Pathogen Detection / CARD 可映射

### A.2 Bioinformatics Plugin SDK

定义插件接口、输入输出契约、元数据、版本管理和注册机制，使第三方开发者可以快速开发新的病原分析插件。

**V0.2 落地**：

- **Snakemake rule** = 最细粒度执行单元
- **Hermes Skill**（SKILL.md + scripts/）= 编排单元
- **MCP server** = 服务单元（暴露外部能力如 PubMLST/CARD 查询）
- 三层 plugin 协同：Skill 决定调用哪个 Snakemake workflow，workflow 内部由 rule 组成

这两项构成 Hermes-bacmap 与传统生信平台（Galaxy / Bactopia / Enterobase）最重要的技术差异，也是平台长期可扩展性的关键。

---

## 附录 B：术语表

| 术语 | 含义 |
|---|---|
| **GO** | Genome Object，平台的统一数据对象 |
| **GOM** | Genome Object Model，GO 的统一规范 |
| **GOS** | Genome Object Service，操作 GO 的 Python 库 |
| **L1/L2/L3** | 分层信任的三层（固定 pipeline / 受控探索 / 自由对话） |
| **三元证据链** | (strain_id, pipeline_version, database_version) |
| **Composite Triplet** | (Subject: [Attr], Relation: [Cond], Object: [Attr]) 复合三元组 |
| **Deterministic Verifier** | 确定性规则校验器（非 LLM） |
| **NLI Reflector** | 自然语言推理校验层（CRAG 模式） |
| **DEC** | Diarrheagenic E. coli，致泻性大肠埃希菌 |
| **ST** | Sequence Type，MLST 序列型 |
| **cgMLST** | core genome MLST，核心基因组 MLST |

---

## 附录 C：关键参考文献与开源项目

### C.1 核心先例

- **GPAS**（91% 解读准确率来源）: [medRxiv 2026.02.18.26346517](https://www.medrxiv.org/content/10.64898/2026.02.18.26346517v1.full-text)
- **Ontology-grounded GraphRAG**（98% 准确率/1.7% 幻觉率）: [ScienceDirect S1532046426000171](https://www.sciencedirect.com/science/article/abs/pii/S1532046426000171)
- **Globus HPC MCP 论文**（agents 失败模式）: [arXiv 2508.18489](https://arxiv.org/abs/2508.18489)
- **BixBench**（LLM 生信任务仅 17% 准确率）: [arXiv 2503.00096](https://arxiv.org/pdf/2503.00096)

### C.2 Snakemake 生态

- **BacWORK**（V0.1 起点）: [github.com/FBi-ANSES/BacWORK](https://github.com/FBi-ANSES/BacWORK)
- **SWAM-g**（条件化分型设计）: [github.com/davis-bc/SWAM-g](https://github.com/davis-bc/SWAM-g)
- **BAGEP**（笔记本级 Snakemake）: [PeerJ 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7597632/)
- **SnapperDB**（PHE 内部 SNP 监测）: [github.com/ukhsa-collaboration/snapperdb](https://github.com/ukhsa-collaboration/snapperdb)
- **SnakeLLM**（LLM + Snakemake 范式）: [github.com/BenedictL/SnakeLLM](https://github.com/BenedictL/SnakeLLM)

### C.3 4 病原专用工具（已替换为 Python 原生实现）

- ~~**ECTyper**（DEC）~~ → **ecoh_serotyper**（Python 原生，782KB DB，委托 gene_scanner）
- **call_pathotype.py**（DEC pathotype 判定）: 内置脚本
- ~~**ShigEiFinder**（Shigella）~~ → **shigella_serotyper**（移植 ShigATyper，58 种血清型）
- ~~**VPsero + Kaptive**（V. para）~~ → **自行开发中**（不采用 Kaptive）
- **pyrodigal**（基因组注释）: pip install pyrodigal（替代 Prokka CLI）
- **Prokka sprot/IS/AMR 数据库**: 复用 Prokka 蛋白库，blastp 注释

### C.4 Hermes Agent 与 LLM

- **Hermes Agent**: [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- **Hermes × NVIDIA**: [NVIDIA RTX AI Garage Blog](https://blogs.nvidia.com/blog/rtx-ai-garage-hermes-agent-dgx-spark/)
- **RTX 5090 LLM Benchmark**: [hardware-corner.net](https://www.hardware-corner.net/rtx-5090-llm-benchmarks/)
- **Ollama vs vLLM 对比**: [insiderllm.com](https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/)

### C.5 RAG 与幻觉控制

- **Self-Correcting RAG**（AP 0.85）: [arxiv 2604.10734](https://www.arxiv.org/pdf/2604.10734) / [github.com/xjiacs/Self-Correcting-RAG](https://github.com/xjiacs/Self-Correcting-RAG)
- **TripleCheck**: [ACL 2025.hcinlp-1.4](https://aclanthology.org/2025.hcinlp-1.4.pdf)
- **MedRule-KG**（100% rule compliance）: [AI-2-ASE 2025](https://ai-2-ase.github.io/papers/CameraReadys%203-41/34/CameraReady/MedRule_KG__A_Knowledge_Graph__Steered_Scaffold_for_Reliable_Mathematical_and_Biomedical.pdf)
- **BenchAMRking**（AMR workflow 不一致）: [BMC Genomics 2025](https://link.springer.com/article/10.1186/s12864-024-11158-5)

### C.6 数据库与基础设施

- **SRAdb**（NCBI SQLite 先例）: [BMC Bioinformatics 2013](https://link.springer.com/article/10.1186/1471-2105-14-19)
- **SRAKE**（FTS5 + vec + MCP）: [pkg.go.dev/github.com/nishad/srake](https://pkg.go.dev/github.com/nishad/srake)
- **sqlite-vec**: [github.com/asg017/sqlite-vec](https://github.com/asg017/sqlite-vec)
- **SQLite 性能调优**: [phiresky blog](https://phiresky.github.io/blog/2020/sqlite-performance-tuning/)

### C.7 监管与合规

- **FDA AI-Enabled Medical Device List**: [fda.gov](https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-enabled-medical-devices)
- **MedAgentBench**（医疗 LLM agent 69.67% 天花板）: [NEJM AI 2025](https://ai.nejm.org/doi/full/10.1056/AIdbp2500144)
- **PulseNet cgMLST 阈值**: [Frontiers Microbiology 2023](https://www.frontiersin.org/journals/microbiology/articles/10.3389/fmicb.2023.1254777/full)

---

**文档版本**：V0.2
**最后更新**：2026-06-27
**变更说明**：基于 4 轮架构调研（Hermes Agent 能力、Helix.AI production 模式、MCP 长任务适用性、RAG 幻觉控制、Snakemake 病原生态、本地 LLM 硬件）定稿。V0.1 → V0.2 主要收敛架构、明确 4 病原 MVP 范围、引入三层防御与分层信任。新增 §12 开发质量保证（TDD/分析验证/CI/CD/安全测试）。
