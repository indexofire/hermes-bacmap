# 系统概览

Hermes-bacmap 采用**分层架构**：LLM 编排在顶层，工具与技能在中层，固定管线与数据模型在底层。每一层职责清晰、可独立替换。

## 分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4 · 用户接口                                              │
│  Hermes Agent（自然语言） · CLI 脚本 · Web UI（FastAPI）          │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Layer 3 · 工具与技能                                            │
│  18 Hermes Tools（8 生信原语 + 10 高层分析）                      │
│  4 Skills（bio-router / run-pipeline / interpret-results / ...） │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Layer 2 · 执行引擎                                             │
│  Engine 抽象层（SequenceMatcher + ReadMapper + Hit + Registry） │
│  Deterministic Verifier（三层 AI 防御）                          │
│  Snakemake DAG（24 rules，per-sample + cohort）                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Layer 1 · 数据与存储                                           │
│  Genome Object Model（SQLite + WAL + FTS5）                      │
│  本地文件系统（FASTQ / FASTA / VCF / BAM / HTML）                │
└─────────────────────────────────────────────────────────────────┘
```

| 层 | 职责 | 可替换性 |
|---|---|---|
| L4 用户接口 | 接收输入、展示结果 | 三种入口并行，互不依赖 |
| L3 工具技能 | LLM 调用的原子能力 + 领域知识 | 工具独立注册，Skills 渐进加载 |
| L2 执行引擎 | 算法封装、规则校验、管线编排 | Engine 后端可换（blastn/minimap2/bwa） |
| L1 数据存储 | 持久化、版本管理、检索 | SQLite → PostgreSQL 迁移路径预留 |

## 数据流

一株样本从 FASTQ 到报告的完整流转：

```
FASTQ (Illumina PE)
  │
  ▼
fastp 质控 ──────────────────► qc_fastp.json
  │
  ▼
Shovill 组装 ────────────────► contigs.fasta
  │                              │
  │                              ▼
  │                          assembly_stats.tsv
  │                              │
  ▼                              ▼
species_identify ◄────────── BLAST vs species_markers
  │  (invA/uidA/ipaH/toxR/tlh 一次调用)
  │
  ├─ invA+  ─► Salmonella 路由 ─► gmlst + SISTR
  ├─ uidA+  ─► DEC 路由 ──────► ecoh_serotyper + pathotype
  ├─ ipaH+  ─► Shigella 路由 ─► shigella_serotyper
  └─ toxR+tlh+ ► V.para 路由 ─► tdh/trh 毒力
  │
  ▼
abricate ×3 (CARD / VFDB / PlasmidFinder)
  │
  ▼
pyrodigal + Prokka DB 注释 ─► annotation.json
  │
  ▼
collect_summary.py ─────────► {sample}_summary.json
  │
  ▼
ingest_results.py ──────────► GOM (SQLite)
  │
  ▼
generate_report.py ─────────► {sample}_report.html
```

多样本时额外触发 cohort SNP 流程：

```
每株 snp_calling (BWA → BAM)
  ▼
joint_variant_calling (7 BAM → joint VCF)
  ▼
snp_matrix (VCF → FASTA，whole-genome)
  ▼
phylo_tree (IQ-TREE GTR + UFBoot 1000)
  ▼
snp_summary (距离矩阵 + Newick → JSON)
```

## 技术选型

| 层 | 技术 | 选型理由 |
|---|---|---|
| LLM 推理 | API-key 模式（GLM-5.2 via Z.AI） | 无需 GPU，部署简单；可切本地（Ollama/vLLM/llama.cpp） |
| 工作流引擎 | **Snakemake 7.32** | Python DSL，AI 可生成/修改规则；天然 DAG |
| 元数据存储 | **SQLite + WAL + FTS5** | 零运维、单文件、Hermes 兼容；FTS5 全文检索内置 |
| 文件存储 | 本地文件系统 | 简单可靠；V1.0+ 可迁 MinIO（S3 URI） |
| 序列算法 | **engine/ 抽象层**（SequenceMatcher + ReadMapper） | 解耦管线逻辑与具体 CLI（blastn/minimap2/bwa 可换） |
| 注释 | **pyrodigal + Prokka DB（blastp）** | 纯 Python CDS 预测，替代 Prokka CLI（Perl 依赖重） |
| 包管理 | **uv（Python）+ pixi（生信工具）** | 分离 Python 依赖与生信 CLI，避免 Conda 污染 |
| 测试 | pytest + ruff + mypy --strict | TDD，96 测试全绿 |

## 三层 AI 防御

病原分析涉及公卫合规，平台对 LLM 生成结果执行三层校验：

```
LLM 生成
  ↓
Layer 1 · JSON Schema 校验        schemas.py 定义 24 个 tool 的输入输出契约
  ↓
Layer 2 · Deterministic Verifier  确定性规则校验（species/MLST/serotype/AMR）
  ↓
Layer 3 · AI 解读                  Skills 知识库（interpret-results）
```

| 校验类别 | 规则示例 | 失败处理 |
|---|---|---|
| Species | `species_verdict` 必须包含 "Salmonella" | FAIL |
| MLST | `mlst` 字段非空且有 ST 数字 | WARN |
| Serotype | `serotype.sistr` 非空 | WARN |
| AMR | 关键基因（CTX-M/NDM/KPC/mcr-1）触发审核 | NEEDS_REVIEW |

详见 [Deterministic Verifier](gom.md) 与 `src/hermes_bacmap/deterministic_verifier.py`。

## 核心 Python 模块

| 模块 | 行数 | 职责 |
|---|---|---|
| `tools/` | 2115 | 24 个 Hermes tool handler（7 文件包 + 表驱动注册） |
| `genome_object_service.py` | 667 | GOM：SQLite CRUD + 版本 + 事件 + 文件 + FTS5 |
| `schemas.py` | 844 | 24 个 tool 的 JSON Schema 定义 |
| `genome_annotator.py` | 280 | 基因组注释（pyrodigal + Prokka DBs） |
| `engine/` | 1121 | 算法抽象层（8 个文件） |
| `gene_scanner.py` | 546 | 通用基因扫描引擎（委托 engine.SequenceMatcher） |
| `shigella_serotyper.py` | 231 | Shigella 血清型（58 种） |
| `deterministic_verifier.py` | 216 | 四层确定性规则校验 |
| `species_identifier.py` | 122 | 五基因合并物种鉴定 |
| `ecoh_serotyper.py` | 134 | E. coli O:H 血清型 |
| `__init__.py` | 28 | 插件注册（表驱动，24 tools + 4 skills） |

## 项目目录

```
hermes-bacmap/
├── src/hermes_bacmap/           Hermes 插件 Python 包
│   ├── engine/                  算法抽象层（8 文件，800 行）
│   ├── tools/                   Tool handler 包（seq / cli / pipeline / services）
│   ├── schemas.py               Tool JSON Schema
│   ├── genome_object_service.py GOM
│   ├── deterministic_verifier.py 校验
│   └── ...
├── workflows/bacmap/        Snakemake 流程
│   ├── Snakefile                主入口
│   ├── rules/                   10 个 .smk（23 rules）
│   └── scripts/                 collect_summary / SNP matrix
├── scripts/                     编排脚本（run_analysis / ingest / report）
├── skills/                      4 个 Hermes Skills
├── tests/                       1014 tests
├── data/reference/              13 个参考数据库
├── web/                         FastAPI Web UI
├── pixi.toml                    生信工具依赖
└── pyproject.toml               Python 依赖
```

深入各层：

- [Engine 引擎层](engine.md) — SequenceMatcher / ReadMapper / Hit / Registry
- [GOM 数据模型](gom.md) — SQLite schema、版本管理、事件流
- [Snakemake 管线](pipeline.md) — 24 rules、DAG、物种路由、SNP 流程
- [Skills 技能系统](skills.md) — 4 skills、三层渐进加载、bio-router 决策树
