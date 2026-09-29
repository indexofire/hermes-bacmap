# Environment Setup

This page lists all hardware, operating system, and software dependencies required to run Hermes-bacmap. Once this page is done, continue with [Quick Installation](quick-start.md).

## Hardware Requirements

| Profile | Minimum | Recommended | Comfortable (batch / local LLM) | Full-featured (Kraken2 + GTDB-Tk) |
|---|---|---|---|---|
| CPU | 4 cores x86_64 | 8 cores | 16+ cores | 32+ cores (kraken2-build and GTDB-Tk pplacer run in parallel) |
| RAM | 16 GB | 32 GB | 64 GB | **≥140 GB** (hard gate for GTDB-Tk classify; the download script refuses automatically when insufficient) |
| Disk | 20 GB (SSD) | 50 GB (SSD) | 100 GB+ NVMe | **≥350 GB** NVMe (panel 12 GB + kraken2 library 6 GB + GTDB-Tk R232 98 GB + decompression buffer + results) |
| GPU | Not required | Not required | Optional, ≥16 GB VRAM (local LLM) | Same as left (GTDB-Tk / Kraken2 are both pure CPU) |
| Network | Needed during download | Same as left | Can go offline after switching to local inference | Needed during download (one-time 98 GB GTDB-Tk download) |

> **Full-featured tier note**: this tier is required only when you enable `species_mode=standard` (GTDB-Tk gold-standard arbitration) and `kraken2_prefilter` (reads-level pre-screening + human-read removal).
> All four species identification modes — marker / panel / mash / sourmash — run fully on the "comfortable" tier.
> The 140 GB RAM requirement of GTDB-Tk is a hard constraint — the `download_db_gtdbtk.py` download script pre-checks MemAvailable and refuses to install when it falls short.

## Operating System

| OS | Support | Notes |
|---|---|---|
| **Linux x86_64** | Officially supported | Tested on Ubuntu 22.04 / Debian 12 / Rocky 9 |
| macOS (arm64) | Unofficial | Most pixi bioinformatics tools are x86_64-native; arm requires Rosetta |
| Windows / WSL2 | Not supported | Some pixi packages have no Windows builds; Linux is recommended |

## Software Dependencies

### Package Management Tools

| Tool | Version | Purpose |
|---|---|---|
| [pixi](https://pixi.sh) | ≥ 0.30 | Bioinformatics CLIs + Python runtime (the only thing production users need) |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.3 | Python dev tools (developers only: pytest / ruff / mypy) |

### Python Environment

| Item | Requirement |
|---|---|
| Python | **3.12** (installed automatically by pixi; unified across runtime and development) |

Core Python dependencies (declared in `pyproject.toml`, pulled automatically by `pixi install`):

| Package | Version | Purpose |
|---|---|---|
| biopython | ≥ 1.83 | Sequence manipulation |
| pydantic | ≥ 2.0 | Data models / tool schemas |
| pyrodigal | ≥ 3.0 | Genome annotation (replaces the Prokka CLI) |
| mappy | ≥ 2.24 | minimap2 Python bindings |
| sourmash | ≥ 4.8 | K-mer comparison (V. para serotyping) |

### Bioinformatics Tools (pixi)

`pixi install` automatically pulls all of the following CLI tools into the project-local environment:

| Tool | Version | Purpose |
|---|---|---|
| fastp | ≥ 1.3.5 | FASTQ QC + adapter trimming |
| shovill | ≥ 1.1.0 | Genome assembly (SPAdes backend) |
| blast | ≥ 2.16 | Local BLAST (species identification / gene scanning) |
| bwa | ≥ 0.7.17 | Read alignment (SNP pipeline) |
| samtools | ≥ 1.20 | BAM operations |
| bcftools | ≥ 1.20 | Variant calling (joint calling) |
| seqkit | ≥ 2.8 | Sequence statistics |
| sistr_cmd | ≥ 1.1.3 | Salmonella serotyping |
| abricate | ≥ 1.4.0 | AMR / virulence / plasmid detection |
| iqtree | ≥ 3.1.2 | Maximum-likelihood phylogenetic trees |
| snakemake | 7.32.* | Workflow engine |
| gmlst | 0.1.0 | MLST (PubMLST schemes) |
| prodigal | ≥ 2.6 | CDS prediction (pyrodigal backend) |

### Optional: Standard Species Identification (CheckM2 + GTDB-Tk)

By default, species are identified quickly via target genes. For the standard regime (genome contamination checking + taxonomic validation), install the following external databases:

| Database | Size | Environment variable | Download |
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

When the environment variables are not set, `species_mode: standard` automatically falls back to `simple` (target genes only).

### Optional: GPU and Local LLM

Configure a local LLM only when you need offline inference or your data must not leave the premises; see [Local LLM Configuration](local-llm.md).

| GPU VRAM | Recommended model | Provider |
|---|---|---|
| 8 GB | Qwen3-7B | Ollama / llama.cpp (Q4 quantization) |
| 16 GB | Qwen3-14B | Ollama / vLLM / llama.cpp |
| 24 GB+ | Qwen3-32B | vLLM |

Without a GPU, the cloud Z.AI (GLM-5.2) is used by default — zero GPU required to run.

## Dual-Environment Architecture

Hermes-bacmap uses two mutually isolated environments:

| Environment | Manager | Python | Contents |
|---|---|---|---|
| `.pixi/envs/default` | pixi | 3.12 | Bioinformatics CLIs + all Python runtime dependencies (biopython, pyrodigal, gmlst, etc.) |
| `.venv` | uv | 3.12 | Dev tools (pytest, ruff, mypy) — developers only |

```bash
# 生产用户只需 pixi
pixi install

# 开发者额外需要 uv
uv venv --python 3.12
uv pip install -e ".[dev]"
```

With the environments ready, continue with [Quick Installation](quick-start.md) to build database indexes and deploy the plugin.
