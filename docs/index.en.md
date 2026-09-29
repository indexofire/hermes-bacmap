# Hermes-bacmap

> **AI-native intelligent genome analysis platform for pathogenic microorganisms** — a natural-language-driven WGS analysis system designed for small and medium-sized public health laboratories.

Hermes-bacmap uses the [Hermes Agent](https://github.com/NousResearch/hermes-agent) as its orchestration core,
unifying Snakemake workflows, 26 bioinformatics tools, a SQLite data model, and local LLM inference
into a single platform. With natural language (Chinese or English), users can complete the entire
workflow from FASTQ upload to outbreak trace-back.

## Core Features

- **Natural language interaction** — "analyze this Salmonella isolate", "compare SNPs with the last
  outbreak strains", "generate the AMR report" — Hermes Agent automatically routes to the
  corresponding tools and skills.
- **End-to-end for four pathogens** — Salmonella (full pipeline + SNP phylogeny), DEC/E. coli,
  Shigella/EIEC, and V. parahaemolyticus; after species identification, samples are automatically
  routed to the corresponding pipeline.
- **Three-layer AI defense** — LLM-generated results pass JSON Schema validation → Deterministic
  Verifier rule-based validation → AI interpretation; critical AMR genes (CTX-M/NDM/KPC/mcr-1)
  require mandatory human review.
- **Traceable audit** — the Genome Object Model (GOM) stores all results in SQLite + WAL + FTS5;
  every conclusion carries a three-part evidence chain (strain_id, pipeline_version,
  database_versions), with immutable, versioned objects.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│            User (natural language: Chinese / English)       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                ┌──────────▼──────────┐
                │   Hermes Agent      │   GLM-5.2 via Z.AI API
                │   (LLM orchestration)│   26 tools + 4 skills
                └──────────┬──────────┘
                           │
          ┌─────────────────┼─────────────────┐
          │                 │                  │
┌────────▼───────┐ ┌───────▼────────┐ ┌──────▼─────────┐
│  L1 pipelines  │ │  L2 validation │ │  L3 AI insights│
│  Snakemake DAG │ │  Verifier      │ │ Skills + search│
│  30 rules      │ │  21 tests      │ │  FTS5 + KB     │
└────────┬───────┘ └───────┬────────┘ └──────┬─────────┘
          │                 │                  │
          └─────────────────┼──────────────────┘
                           │
                ┌──────────▼──────────┐
                │  Genome Object      │   SQLite + WAL + FTS5
                │  Model (GOM)        │   4 tables, 5 indexes
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │  Local filesystem   │   FASTQ / FASTA / VCF / BAM
                └─────────────────────┘
```

## Project Scale

| Dimension | Count | Description |
|---|---|---|
| Hermes Tools | **24** | 8 bioinformatics primitives + 16 high-level analysis tools |
| Snakemake Rules | **25** | per-sample DAG + cohort SNP DAG (3 species groups) |
| Test cases | **1415** | GOM + trace-back index + Verifier + Engine + Utils, all green |
| Supported pathogens | **4** | Salmonella / DEC / Shigella / V. parahaemolyticus |
| Skills | **4** | bio-router / run-pipeline / interpret-results / bioinfo-analysis |
| Reference databases | **15** | Species identification + AMR + virulence + serotype + SNP references + Prokka annotation |

## 3-Minute Quick Start

```bash
# 1. 克隆仓库
git clone https://github.com/indexofire/hermes-bacmap.git
cd hermes-bacmap

# 2. 生信 CLI 工具 (pixi, 含 Python 3.12 + 全部依赖)
pixi install

# 3. 安装插件到 Hermes (entry-point 自动注册)
pip install -e . --python ~/.hermes/hermes-agent/venv/bin/python
hermes plugins enable hermes_bacmap

# 4. 验证安装
pixi run snakemake --version    # 应输出 7.32.x
uv run pytest -q                # 1415 tests 全过

# 5. 启动 Hermes Agent
hermes chat
> 列出所有样本                    # bio_list_samples
> 分析 SAM-TYP-001               # 端到端流程
```

For full hardware requirements, dependency installation, and database downloads, see [Environment Preparation](installation/environment.md) and [Quick Installation](installation/quick-start.md).

## Next Steps

| Section | Audience | Content |
|---|---|---|
| [Installation Guide](installation/environment.md) | Ops / first-time deployment | Hardware requirements, dual uv + pixi environments, reference databases |
| [Usage Guide](usage/cli.md) | Lab operators | CLI scripts, Hermes Agent conversations, Web UI |
| [Architecture Design](architecture/overview.md) | Developers / evaluators | Layered architecture, Engine layer, GOM data model, Snakemake pipeline |
| [Case Studies](cases/single-sample.md) | Everyone | Single-isolate analysis walkthrough, 7-isolate outbreak investigation |
| [Reference](reference/tools.md) | Developers | 18-tool list, 13 databases, troubleshooting |

!!! tip "First time?"
    Recommended order: [Environment Preparation](installation/environment.md) →
    [Quick Installation](installation/quick-start.md) →
    [Single-Isolate Analysis Case](cases/single-sample.md) →
    [Hermes Agent Interaction](usage/hermes-agent.md).
