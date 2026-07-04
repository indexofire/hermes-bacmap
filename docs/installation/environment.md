# 环境准备

本页列出运行 Hermes-bacmap 所需的全部硬件、操作系统与软件依赖。完成本页后即可进入[快速安装](quick-start.md)。

## 硬件要求

| 配置 | 最低 | 推荐 | 舒适（批量 / 本地 LLM） |
|---|---|---|---|
| CPU | 4 核 x86_64 | 8 核 | 16 核+ |
| RAM | 16 GB | 32 GB | 64 GB |
| 磁盘 | 20 GB（SSD） | 50 GB（SSD） | 100 GB+ NVMe |
| GPU | 不需要 | 不需要 | 可选，≥16 GB VRAM（本地 LLM） |
| 网络 | 下载阶段需要 | 同左 | 本地推理后可离线 |

!!! note "为何 RAM 要求较高"
    Shovill（SPAdes 组装）单株峰值约 8–16 GB；SNP 联合变异检测（bcftools mpileup）对多样本 BAM 同时读取。推荐档可流畅完成 96 株/run 批处理。

## 操作系统

| OS | 支持 | 说明 |
|---|---|---|
| **Linux x86_64** | 官方支持 | Ubuntu 22.04 / Debian 12 / Rocky 9 测试通过 |
| macOS (arm64) | 非官方 | pixi 生信工具多为 x86_64 原生，arm 需 Rosetta |
| Windows / WSL2 | 不支持 | pixi 部分包无 Windows 构建，建议用 Linux |

!!! warning "Snakemake 版本锁定"
    必须使用 **Snakemake 7.32.x**。v8+ 的锁机制与 CLI 行为有破坏性变更，会导致管线失败。

## 软件依赖

### Python 环境（uv）

| 项 | 要求 |
|---|---|
| Python | **3.11+**（主开发环境） |
| Python 3.12 | gmlst 独立环境需要（`.venv-gmlst`） |
| 包管理 | [uv](https://docs.astral.sh/uv/) ≥ 0.3 |

核心 Python 依赖（`pyproject.toml`）：

| 包 | 版本 | 用途 |
|---|---|---|
| biopython | ≥ 1.83 | 序列操作 |
| pydantic | ≥ 2.0 | 数据模型 / Tool schema |
| pytest | ≥ 8.0 | 测试 |
| ruff | ≥ 0.5 | lint + format |
| mypy | ≥ 1.10 | 类型检查（--strict） |

### 生信工具（pixi）

`pixi install` 自动拉取以下全部 CLI 工具到项目本地环境：

| 工具 | 版本 | 用途 |
|---|---|---|
| fastp | ≥ 1.3.5 | FASTQ 质控 + adapter trimming |
| shovill | ≥ 1.1.0 | 基因组组装（SPAdes 后端） |
| blast | ≥ 2.16 | 本地 BLAST（物种鉴定 / 基因扫描） |
| bwa | ≥ 0.7.17 | 读段比对（SNP 管线） |
| samtools | ≥ 1.20 | BAM 操作（9 个子命令） |
| bcftools | ≥ 1.20 | 变异检测（联合 calling） |
| seqkit | ≥ 2.8 | 序列统计 |
| sistr_cmd | ≥ 1.1.3 | Salmonella 血清型 |
| abricate | ≥ 1.4.0 | AMR / 毒力 / 质粒检测 |
| iqtree | ≥ 3.1.2 | 最大似然系统发育树 |
| snakemake | 7.32.* | 工作流引擎 |
| gmlst | 0.1.0 | MLST（独立 Python 3.12 环境） |

### 可选：Web UI 依赖

| 工具 | 版本 | 用途 |
|---|---|---|
| Node.js | ≥ 18 | 前端构建（如需修改 React 资源） |

Web UI 后端（FastAPI + uvicorn）随 Python 主环境安装，前端静态资源已预编译到 `web/static/`，无需 Node.js 即可运行。

### 可选：GPU 与本地 LLM

仅当需要离线推理或数据不出境时才配置本地 LLM，详见[本地 LLM 配置](local-llm.md)。

| GPU VRAM | 推荐模型 | Provider |
|---|---|---|
| 8 GB | Qwen3-7B | Ollama / llama.cpp（Q4 量化） |
| 16 GB | Qwen3-14B | Ollama / vLLM / llama.cpp |
| 24 GB+ | Qwen3-32B | vLLM |

无 GPU 时默认使用云端 Z.AI（GLM-5.2），零 GPU 即可运行。

## 三套环境概览

Hermes-bacmap 使用三个相互隔离的环境，避免依赖冲突：

| 环境 | 管理工具 | Python | 内容 |
|---|---|---|---|
| `.venv` | uv | 3.11 | Hermes 插件、biopython、pydantic、FastAPI、测试 |
| `.pixi/envs/default` | pixi | — | 生信 CLI 工具（blast / bwa / samtools / ...） |
| `.venv-gmlst` | uv | 3.12 | 仅 gmlst（上游要求 Python ≥ 3.12） |

```bash
# 验证三套环境
source .venv/bin/activate && python -c "import hermes_bacmap"   # 主环境
pixi run snakemake --version                                     # pixi 环境
.venv-gmlst/bin/gmlst --version                                  # gmlst 环境
```

三套环境就绪后，进入[快速安装](quick-start.md)下载参考数据库并验证。
