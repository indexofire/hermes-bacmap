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
详细环境搭建见 **[docs/installation/environment.md](docs/installation/environment.md)**。

## 支持的病原

| 病原 | 物种鉴定 | 血清型 | MLST | AMR | SNP/系统发育 | 状态 |
|---|---|---|---|---|---|---|
| **Salmonella** | invA (marker) / GTDB-Tk (standard) | SISTR | gmlst (salmonella_2) | abricate (CARD/VFDB/PlasmidFinder) | bwa+bcftools+iqtree | ✅ V0.3 |
| **DEC** (E. coli) | uidA (marker) / GTDB-Tk (standard) | ecoh_serotyper (Python) | gmlst | abricate | bwa+bcftools+iqtree | ✅ V0.2 |
| **Shigella / EIEC** | ipaH (marker) / GTDB-Tk (standard) | shigella_serotyper (58 serotypes) | gmlst | abricate | bwa+bcftools+iqtree | ✅ V0.2 |
| **V. parahaemolyticus** | toxR + tlh (marker) / GTDB-Tk (standard) | VpaSerotyper (Python) | gmlst | abricate | bwa+bcftools+iqtree | ✅ V0.4 (物种鉴定) |

## 核心模块

| 模块 | 行数 | 功能 |
|---|---|---|
| `tools/` | 2399 | 27 个 Hermes tool handler（seq / cli / pipeline / services 分包 + registry 表驱动注册） |
| `services/genome_object_service.py` | 749 | GOM（SQLite + 版本管理 + 事件 + 文件产物 + FTS5 搜索） |
| `schemas.py` | 936 | 27 个 tool JSON Schema 定义 |
| `analysis/genome_annotator.py` | 280 | 基因组注释（pyrodigal + Prokka DBs，Python 原生） |
| `engine/` | 1125 | 算法抽象层（SequenceMatcher + ReadMapper + Hit，backends/：blast / minimap2 / kma / kmer 可换后端） |
| `analysis/gene_scanner.py` | 545 | 基因扫描引擎（委托 engine.SequenceMatcher） |
| `analysis/nli_reflector.py` | 413 | Layer 3 NLI Reflector（原子声明蕴含/矛盾校验 + 审计事件） |
| `typing/shigella_serotyper.py` | 231 | Shigella 血清型（移植 ShigATyper） |
| `typing/vpa_serotyper_engine.py` | 450 | V. parahaemolyticus O/K 血清型（移植 vpautils） |
| `analysis/deterministic_verifier.py` | 222 | 确定性规则校验（species/MLST/serotype/AMR） |
| `analysis/species_identifier.py` | 123 | 物种鉴定（marker genes：invA/uidA/ipaH/toxR/tlh 五基因 1 次 BLAST；GTDB-Tk 标准模式在 `analysis/taxonomic_validator.py`） |
| `typing/ecoh_serotyper.py` | 134 | E. coli O:H 血清型（委托 gene_scanner） |

> 模块路径均相对 `src/hermes_bacmap/`。另有 `services/strain_index.py`（菌株检索 + FTS5）、`analysis/cgmlst_*.py`（cgMLST 溯源投影/距离）、`analysis/failure_diagnostics.py`（9 种失败模式诊断）等，详见 [docs/features.md](docs/features.md)。

## 项目结构

```
hermes-bacmap/
├── src/hermes_bacmap/           Hermes 插件 Python 包
│   ├── __init__.py             插件注册（27 tools 表驱动 + skills 自动发现）
│   ├── schemas.py              27 个 tool JSON Schema 定义
│   ├── tools/                  Tool handler 包（seq / cli / pipeline / services + registry 表驱动注册）
│   ├── engine/                 算法抽象层（SequenceMatcher / ReadMapper + backends/ 可换后端）
│   ├── analysis/               领域分析（物种鉴定 / 基因扫描 / 注释 / 确定性校验 / cgMLST / NLI / 失败诊断）
│   ├── typing/                 血清型模块（ecoh / shigella / vpa）
│   ├── services/               GOM + 菌株索引 / 菌株元数据 / 实验室结果
│   └── skills/                 6 个 Hermes Skills（随 wheel 打包）
│       ├── bio-router/             始终加载的 skill 路由器
│       ├── run-pipeline/           跨病原管线操作指南 + 5 个 references
│       ├── bioinfo-analysis/       通用生信决策树
│       ├── interpret-results/      结果解读知识库 + 2 个 references
│       ├── seqkit-operations/      seqkit 序列操作
│       └── ncbi-datasets/          NCBI 基因组数据获取
├── workflows/bacmap/        Snakemake 分析流程
│   ├── Snakefile               主入口（per-sample + cohort DAG）
│   ├── config/                 配置 + 样本表
│   ├── rules/                  11 个 rule 文件（29 rules：25 常规 + 4 cgMLST cohort 门控，+ Snakefile `rule all` 共 30）
│   └── scripts/                collect_summary + SNP/cgMLST cohort 脚本 + pathotype
├── scripts/                     编排脚本
│   ├── run_analysis.py         端到端编排器（--sample/--all/--snp/--status）
│   ├── ingest_results.py       GOM 入库（--sample/--all/--snp）
│   ├── generate_report.py      HTML/PDF 报告（--sample/--all/--cohort）
│   ├── validate_analytical.py  分析验证 harness（vs gold standard）
│   ├── build_cgmlst_reference.py  cgMLST 本地参考库构建
│   └── ...                     ENA 下载 / 元数据导入 / 基准 / LLM 切换
├── web/                         FastAPI Web UI（app.py + 单页模板，X-API-Key 认证）
├── tests/                       测试（1415 tests）
│   ├── unit/                   GOM + Verifier + Engine + Cohort TDD
│   ├── conftest.py             共享 fixtures
│   └── fixtures/gold_standard/ 12 株 gold standard 数据集（9 株经验证 harness）
├── data/reference/              参考数据库（8 类：amr / annotation / genomes / plasmid / serotype / species / virulence / vpa_serotype）
├── metadata_profiles/           样本元数据模板（default / cdc_china）
├── docs/                        mkdocs 文档站
│   ├── features.md             ← 完整功能文档
│   ├── architecture/           overview / engine / GOM / pipeline / skills / data-model
│   └── installation/ · usage/ · pathogens/ · cases/ · reference/
├── mkdocs.yml                   文档站导航配置
├── pixi.toml                    生信工具依赖
├── pyproject.toml               Python 依赖
└── project.md                   开发计划（V0.7, 1176 行）
```

## 环境架构

| 工具 | 管理内容 | 说明 |
|------|---------|------|
| **pixi** | 生信 CLI + Python 运行时 | fastp, Shovill, blast, bwa, samtools, bcftools, seqkit, iqtree, pyrodigal, snakemake, gmlst, mash, skani, kraken2, bracken, biopython, pyrodigal, mappy, sourmash |
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
