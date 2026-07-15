# hermes-bacmap

AI Native 病原微生物基因组智能分析平台 — [Hermes Agent](https://github.com/NousResearch/hermes-agent) 插件。

## 快速开始

1. 参照[Hermes Agent](https://hermes-agent.nousresearch.com/)安装说明完成[Hermes](https://hermes-agent.nousresearch.com)的安装。

2. 下载源代码并安装生信依赖

```bash
git clone https://github.com/indexofire/hermes-bacmap.git
cd hermes-bacmap
pixi install
```

3. 将插件安装到 Hermes

```bash
# 安装到 Hermes 的 Python 环境（自动注册 entry-point + 依赖）
pip install -e . --python ~/.hermes/hermes-agent/venv/bin/python

# 启用插件
hermes plugins enable hermes_bacmap
```

4. 启动hermes

启动`hermes agent`后，可以与其交互，开始让AI帮助进行食源性病原微生物的菌株基因组分析工作。

```bash
hermes chat
```

---

## 开发环境

```bash
# 1. 生信环境 (pixi，含所有运行时依赖 + Python 库)
pixi install

# 2. 启动 Hermes Agent
hermes chat
```

生产用户只需 `pixi install`。开发者额外执行：
```bash
# 3. Python 开发工具 (uv，仅 pytest/ruff/mypy)
uv venv --python 3.12
uv pip install -e ".[dev]"
```

详细功能文档见 **[docs/features.md](docs/features.md)**。
详细环境搭建见 **[docs/hermes-chat-guide.md](docs/hermes-chat-guide.md)**。

## 支持的病原

| 病原 | 物种鉴定靶基因 | 血清型 | MLST | AMR | SNP/系统发育 | 状态 |
|---|---|---|---|---|---|---|
| **Salmonella** | invA | SISTR | gmlst (salmonella_2) | abricate (CARD/VFDB/PlasmidFinder) | bwa+bcftools+iqtree | ✅ V0.3 |
| **DEC** (E. coli) | uidA | ecoh_serotyper (Python) | gmlst | abricate | bwa+bcftools+iqtree | ✅ V0.2 |
| **Shigella / EIEC** | ipaH | shigella_serotyper (58 serotypes) | gmlst | abricate | bwa+bcftools+iqtree | ✅ V0.2 |
| **V. parahaemolyticus** | toxR + tlh | native | gmlst | abricate | bwa+bcftools+iqtree | ✅ V0.4 (物种鉴定) |

## 核心模块

| 模块 | 行数 | 功能 |
|---|---|---|
| `tools.py` | 1572 | 17 个 Hermes tool handler |
| `genome_object_service.py` | 644 | GOM（SQLite + 版本管理 + 事件 + 文件产物 + FTS5 搜索） |
| `schemas.py` | 575 | 17 个 tool JSON Schema 定义 |
| `genome_annotator.py` | 288 | 基因组注释（pyrodigal + Prokka DBs，Python 原生） |
| `engine/` | 800 | 算法抽象层（SequenceMatcher + ReadMapper + Hit） |
| `gene_scanner.py` | 420 | 基因扫描引擎（委托 engine.SequenceMatcher） |
| `shigella_serotyper.py` | 207 | Shigella 血清型（移植 ShigATyper） |
| `deterministic_verifier.py` | 186 | 确定性规则校验（species/MLST/serotype/AMR） |
| `species_identifier.py` | 121 | 统一物种鉴定（invA/uidA/ipaH/toxR/tlh） |
| `ecoh_serotyper.py` | 121 | E. coli O:H 血清型（委托 gene_scanner） |

## 项目结构

```
hermes-bacmap/
├── src/hermes_bacmap/           Hermes 插件 Python 包
│   ├── __init__.py             插件注册（17 tools + 4 skills）
│   ├── schemas.py              Tool JSON Schema 定义
│   ├── tools.py                Tool handler 实现
│   ├── genome_object_service.py  GOM（SQLite + 版本管理）
│   └── deterministic_verifier.py  确定性规则校验
├── workflows/salmonella/        Snakemake 分析流程
│   ├── Snakefile               主入口（per-sample + cohort DAG）
│   ├── config/                 配置 + 样本表
│   ├── rules/                  8 个 rule 文件（21 rules）
│   └── scripts/                collect_summary + SNP matrix + pathotype
├── scripts/                     编排脚本
│   ├── run_analysis.py         端到端编排器（--sample/--all/--snp/--status）
│   ├── ingest_results.py       GOM 入库（--sample/--all/--snp）
│   ├── generate_report.py      HTML 报告（--sample/--all/--cohort）
│   ├── download_gold_standard.py  ENA FASTQ 下载
│   └── ...
├── skills/                      Hermes Skills（4 个）
│   ├── bio-router/             始终加载的 skill 路由器
│   ├── run-pipeline/           跨病原管线操作指南 + 5 个 references
│   ├── bioinfo-analysis/       通用生信决策树
│   └── interpret-results/      结果解读知识库 + 2 个 references
├── tests/                       测试（96 tests）
│   ├── unit/                   GOM + Verifier + Cohort TDD
│   ├── conftest.py             共享 fixtures
│   └── fixtures/gold_standard/ 10 株验证数据集
├── data/reference/              参考数据库（15 个 FASTA）
├── docs/                        开发文档
│   ├── features.md             ← 完整功能文档
│   ├── gom-architecture.md     GOM 架构设计
│   ├── getting-started.md      环境搭建
│   └── hermes-chat-guide.md    Hermes 交互指南
├── pixi.toml                    生信工具依赖
├── pyproject.toml               Python 依赖
└── project.md                   开发计划（V0.4, 1176 行）
```

## 环境架构

| 工具 | 管理内容 | 说明 |
|------|---------|------|
| **pixi** | 生信 CLI + Python 运行时 | fastp, Shovill, blast, bwa, samtools, bcftools, seqkit, iqtree, prodigal, mash, snakemake, gmlst, biopython, pyrodigal, mappy, sourmash |
| **uv** (可选) | Python 开发工具 | pytest, ruff, mypy（仅开发者需要） |
| **Hermes Agent** | LLM 编排 | API-key 模式（GLM-5.2 via Z.AI） |

## 日常开发

```bash
# 跑测试
uv run pytest -v

# 代码检查
uv run ruff check src/ tests/

# 分析单株
python scripts/run_analysis.py --sample SAM-TYP-001

# 批量分析所有样本
python scripts/run_analysis.py --all

# GOM 入库
python scripts/ingest_results.py --all

# 生成报告
python scripts/generate_report.py --all
```

## Hermes 交互

```bash
hermes chat
> 列出所有样本
> 分析 SAM-DEC-012
> SAM-SHI-013 的 ipaH 是阳性吗？
> 比较 SAM-SHI-013 和 SAM-EIEC-014
> 生成 SAM-TYP-001 的报告
```

## 部署到 Hermes

```bash
# 1. 安装插件 + 依赖到 Hermes venv（entry-point 自动注册）
pip install -e . --python ~/.hermes/hermes-agent/venv/bin/python

# 2. 启用插件
hermes plugins enable hermes_bacmap

# 3. 如果数据库不在默认位置，设置环境变量
export BACMAP_DATA_DIR=/path/to/hermes-bacmap/data
```

完整指南见 **[docs/installation/quick-start.md](docs/installation/quick-start.md)**。
