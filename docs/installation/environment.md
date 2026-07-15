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

## 操作系统

| OS | 支持 | 说明 |
|---|---|---|
| **Linux x86_64** | 官方支持 | Ubuntu 22.04 / Debian 12 / Rocky 9 测试通过 |
| macOS (arm64) | 非官方 | pixi 生信工具多为 x86_64 原生，arm 需 Rosetta |
| Windows / WSL2 | 不支持 | pixi 部分包无 Windows 构建，建议用 Linux |

## 软件依赖

### 包管理工具

| 工具 | 版本 | 用途 |
|---|---|---|
| [pixi](https://pixi.sh) | ≥ 0.30 | 生信 CLI + Python 运行时（生产用户唯一需要） |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.3 | Python 开发工具（仅开发者需要：pytest / ruff / mypy） |

### Python 环境

| 项 | 要求 |
|---|---|
| Python | **3.12**（pixi 自动安装，统一用于运行时和开发） |

核心 Python 依赖（`pyproject.toml` 声明，`pixi install` 自动拉取）：

| 包 | 版本 | 用途 |
|---|---|---|
| biopython | ≥ 1.83 | 序列操作 |
| pydantic | ≥ 2.0 | 数据模型 / Tool schema |
| pyrodigal | ≥ 3.0 | 基因组注释（替代 Prokka CLI） |
| mappy | ≥ 2.24 | minimap2 Python 绑定 |
| sourmash | ≥ 4.8 | K-mer 比较（V.para 血清型） |

### 生信工具（pixi）

`pixi install` 自动拉取以下全部 CLI 工具到项目本地环境：

| 工具 | 版本 | 用途 |
|---|---|---|
| fastp | ≥ 1.3.5 | FASTQ 质控 + adapter trimming |
| shovill | ≥ 1.1.0 | 基因组组装（SPAdes 后端） |
| blast | ≥ 2.16 | 本地 BLAST（物种鉴定 / 基因扫描） |
| bwa | ≥ 0.7.17 | 读段比对（SNP 管线） |
| samtools | ≥ 1.20 | BAM 操作 |
| bcftools | ≥ 1.20 | 变异检测（联合 calling） |
| seqkit | ≥ 2.8 | 序列统计 |
| sistr_cmd | ≥ 1.1.3 | Salmonella 血清型 |
| abricate | ≥ 1.4.0 | AMR / 毒力 / 质粒检测 |
| iqtree | ≥ 3.1.2 | 最大似然系统发育树 |
| snakemake | 7.32.* | 工作流引擎 |
| gmlst | 0.1.0 | MLST（PubMLST schemes） |
| prodigal | ≥ 2.6 | CDS 预测（pyrodigal 后端） |

### 可选：标准物种鉴定（CheckM2 + GTDB-Tk）

默认使用靶标基因快速鉴定物种。如需标准规范（基因组污染校验 + 分类学验证），安装以下外部数据库：

| 数据库 | 大小 | 环境变量 | 下载 |
|---|---|---|---|
| CheckM2 DB | ~3 GB | `CHECKM2DB` | [CheckM2](https://github.com/chklovski/CheckM2) |
| GTDB-Tk DB | ~70 GB | `GTDBDB` | [GTDB-Tk](https://github.com/Ecogenomics/GtDBTk) |

```bash
# 安装数据库后设置环境变量
export CHECKM2DB=/data/databases/checkm2_db
export GTDBDB=/data/databases/gtdb_r220

# 或写入 ~/.bashrc 持久化
echo 'export CHECKM2DB=/data/databases/checkm2_db' >> ~/.bashrc
echo 'export GTDBDB=/data/databases/gtdb_r220' >> ~/.bashrc
```

未设置环境变量时，`species_mode: standard` 自动降级为 `simple`（仅靶标基因）。

### 可选：GPU 与本地 LLM

仅当需要离线推理或数据不出境时才配置本地 LLM，详见[本地 LLM 配置](local-llm.md)。

| GPU VRAM | 推荐模型 | Provider |
|---|---|---|
| 8 GB | Qwen3-7B | Ollama / llama.cpp（Q4 量化） |
| 16 GB | Qwen3-14B | Ollama / vLLM / llama.cpp |
| 24 GB+ | Qwen3-32B | vLLM |

无 GPU 时默认使用云端 Z.AI（GLM-5.2），零 GPU 即可运行。

## 双环境架构

Hermes-bacmap 使用两个相互隔离的环境：

| 环境 | 管理工具 | Python | 内容 |
|---|---|---|---|
| `.pixi/envs/default` | pixi | 3.12 | 生信 CLI + 全部 Python 运行时依赖（biopython、pyrodigal、gmlst 等） |
| `.venv` | uv | 3.12 | 开发工具（pytest、ruff、mypy）— 仅开发者需要 |

```bash
# 生产用户只需 pixi
pixi install

# 开发者额外需要 uv
uv venv --python 3.12
uv pip install -e ".[dev]"
```

环境就绪后，进入[快速安装](quick-start.md)构建数据库索引并部署插件。
