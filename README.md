# hermes-bacmap

AI Native 病原微生物基因组智能分析平台 — [Hermes Agent](https://github.com/NousResearch/hermes-agent) 插件。

## 快速开始

```bash
# 1. Python 开发环境 (uv)
uv venv --python 3.11
uv pip install -e ".[dev]"

# 2. 生信 CLI 工具 (pixi)
pixi install

# 3. gmlst (Python 3.12 独立环境)
uv venv .venv-gmlst --python 3.12
uv pip install --python .venv-gmlst/bin/python gmlst

# 4. 启动 Hermes Agent
hermes chat
```

详细环境搭建见 **[docs/hermes-chat-guide.md](docs/hermes-chat-guide.md)**。

## 支持的病原

| 病原 | 物种鉴定靶基因 | 血清型 | MLST | AMR | 状态 |
|---|---|---|---|---|---|
| **Salmonella** | invA | SISTR | gmlst (salmonella_2) | abricate (CARD/VFDB/PlasmidFinder) | ✅ V0.1 |
| **DEC** (E. coli) | uidA | ecoh_serotyper (Python) | gmlst | abricate | ✅ V0.2 |
| **Shigella / EIEC** | ipaH | shigella_serotyper (58 serotypes) | gmlst | abricate | ✅ V0.2 |
| **V. parahaemolyticus** | toxR + tlh | — | — | abricate | ✅ V0.4 (物种鉴定) |

## 核心模块

| 模块 | 行数 | 功能 |
|---|---|---|
| `genome_object_service.py` | 598 | GOM（SQLite + 版本管理 + 事件 + 文件产物） |
| `gene_scanner.py` | 394 | 通用 BLAST 引擎（任意 abricate 格式数据库） |
| `deterministic_verifier.py` | 186 | 确定性规则校验（species/MLST/serotype/AMR） |
| `ecoh_serotyper.py` | 121 | E. coli O:H 血清型（委托 gene_scanner） |
| `shigella_serotyper.py` | 175 | Shigella 血清型（移植 ShigATyper） |
| `species_identifier.py` | 120 | 统一物种鉴定（invA/uidA/ipaH/toxR/tlh） |
| `tools.py` | 1327 | Hermes 插件 14 个 tool handler |

## 项目结构

```
hermes-bacmap/
├── src/hermes_bacmap/           Hermes 插件 Python 包
│   ├── __init__.py             插件注册（13 tools）
│   ├── schemas.py              Tool JSON Schema 定义
│   ├── tools.py                Tool handler 实现
│   ├── genome_object_service.py  GOM（SQLite + 版本管理）
│   └── deterministic_verifier.py  确定性规则校验
├── workflows/salmonella/        Snakemake 分析流程
│   ├── Snakefile               主入口（84 job DAG）
│   ├── config/                 配置 + 样本表
│   ├── rules/                  6 个 rule 文件
│   └── scripts/                collect_summary.py + call_pathotype.py
├── scripts/                     编排脚本
│   ├── run_analysis.py         端到端编排器
│   ├── ingest_results.py       GOM 入库（智能去重）
│   ├── generate_report.py      HTML 报告生成
│   ├── download_gold_standard.py  ENA FASTQ 下载
│   ├── assemble_gold_standard.sh  Shovill 批量组装
│   └── species_validation_invA.sh  invA 物种验证
├── skills/analyze-salmonella/   Hermes Skill
├── tests/                       测试（87 tests）
│   ├── unit/                   GOM + Verifier TDD
│   ├── conftest.py             共享 fixtures
│   └── fixtures/gold_standard/ 10 株验证数据集
├── data/reference/              参考基因（invA/uidA/ipaH）
├── pixi.toml                    生信工具依赖
├── pyproject.toml               Python 依赖
└── project.md                   开发计划（V0.3, 1174 行）
```

## 环境架构

| 工具 | 管理内容 | 说明 |
|------|---------|------|
| **uv** | Python 3.11 开发环境 | biopython, pydantic, pytest, ruff, mypy |
| **pixi** | 生信 CLI 工具 | fastp, Shovill, blast, gmlst, SISTR, abricate, seqkit |
| **.venv-gmlst** | Python 3.12 独立环境 | gmlst（需要 Python ≥3.12） |
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
# 1. 安装依赖到 Hermes venv
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python biopython pydantic

# 2. 链接插件目录
ln -sf ~/repo/github/hermes-bacmap/src/hermes_bacmap ~/.hermes/plugins/hermes_bacmap

# 3. 启用插件
hermes plugins enable hermes_bacmap
```

完整指南见 **[docs/hermes-chat-guide.md](docs/hermes-chat-guide.md)**。
