# System Overview

Hermes-bacmap adopts a **layered architecture**: LLM orchestration at the top, tools and skills in the middle, and fixed pipelines plus the data model at the bottom.
Each layer has clear responsibilities and can be replaced independently.

## Layered Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  Layer 4 · User Interface                                          │
│  Hermes Agent (natural language) · CLI scripts · Web UI (FastAPI)  │
└────────────────────────────┬───────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────┐
│  Layer 3 · Tools & Skills                                          │
│  29 Hermes Tools (8 bio primitives + 21 high-level analyses)       │
│  6 Skills (bio-router / run-pipeline / interpret-results /         │
│  bioinfo-analysis / seqkit-operations / ncbi-datasets)             │
└────────────────────────────┬───────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────┐
│  Layer 2 · Execution Engine                                        │
│  Engine abstraction (SequenceMatcher + ReadMapper + Hit + Registry)│
│  Deterministic Verifier (three-layer AI defense)                   │
│  Snakemake DAG (29 rules, per-sample + cohort,                     │
│  table-driven pathogen registry)                                   │
└────────────────────────────┬───────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────┐
│  Layer 1 · Data & Storage                                          │
│  Genome Object Model (SQLite + WAL + FTS5)                         │
│  Local filesystem (FASTQ / FASTA / VCF / BAM / HTML)               │
└────────────────────────────────────────────────────────────────────┘
```

| Layer | Responsibility | Replaceability |
|---|---|---|
| L4 User interface | Accept input, present results | Three parallel entry points, mutually independent |
| L3 Tools & skills | Atomic capabilities invoked by the LLM + domain knowledge | Tools registered independently, Skills loaded progressively |
| L2 Execution engine | Algorithm encapsulation, rule validation, pipeline orchestration | Engine backends swappable (blastn/minimap2/bwa) |
| L1 Data storage | Persistence, versioning, retrieval | SQLite → PostgreSQL migration path reserved |

## Data Flow

The complete flow of a single sample from FASTQ to report:

```
FASTQ (Illumina PE)
  │
  ▼
fastp QC ─────────────────────────► qc_fastp.json
  │
  ▼
Shovill assembly ─────────────────► contigs.fasta
  │                              │
  │                              ▼
  │                          assembly_stats.tsv
  │                              │
  ▼                              ▼
species_identify ◄────────── BLAST vs species_markers
  │  (invA/uidA/ipaH/toxR/tlh in one call)
  │
  ├─ invA+  ─► Salmonella routing ─► gmlst + SISTR
  ├─ uidA+  ─► DEC routing ────────► ecoh_serotyper + pathotype
  ├─ ipaH+  ─► Shigella routing ──► shigella_serotyper
  └─ toxR+tlh+ ► V.para routing ─────► tdh/trh virulence
  │
  ▼
abricate ×3 (CARD / VFDB / PlasmidFinder)
  │
  ▼
pyrodigal + Prokka DB annotation ─► annotation.json
  │
  ▼
collect_summary.py ────────────────► {sample}_summary.json
  │
  ▼
ingest_results.py ─────────────────► GOM (SQLite)
  │
  ▼
generate_report.py ────────────────► {sample}_report.html
```

With multiple samples, the cohort SNP workflow is additionally triggered:

```
Per-sample snp_calling (BWA → BAM)
  ▼
joint_variant_calling (7 BAM → joint VCF)
  ▼
snp_matrix (VCF → FASTA, whole-genome)
  ▼
phylo_tree (IQ-TREE GTR + UFBoot 1000)
  ▼
snp_summary (distance matrix + Newick → JSON)
```

## Technology Choices

| Layer | Technology | Rationale |
|---|---|---|
| LLM reasoning | API-key mode (GLM-5.2 via Z.AI) | No GPU required, simple deployment; can switch to local (Ollama/vLLM/llama.cpp) |
| Workflow engine | **Snakemake 7.32** | Python DSL, AI can generate/modify rules; native DAG |
| Metadata storage | **SQLite + WAL + FTS5** | Zero-ops, single file, Hermes-compatible; FTS5 full-text search built in |
| File storage | Local filesystem | Simple and reliable; can migrate to MinIO (S3 URI) in V1.0+ |
| Sequence algorithms | **engine/ abstraction layer** (SequenceMatcher + ReadMapper) | Decouples pipeline logic from specific CLIs (blastn/minimap2/bwa swappable) |
| Annotation | **pyrodigal + Prokka DB (blastp)** | Pure-Python CDS prediction, replaces the Prokka CLI (heavy Perl dependencies) |
| Package management | **uv (Python) + pixi (bioinformatics tools)** | Separates Python dependencies from bioinformatics CLIs, avoids Conda pollution |
| Testing | pytest + ruff + mypy --strict | TDD, 96 tests all green |

## Three-Layer AI Defense

Pathogen analysis involves public-health compliance, so the platform applies three layers of validation to LLM-generated results:

```
LLM generation
  ↓
Layer 1 · JSON Schema validation    schemas.py defines input/output contracts for 24 tools
  ↓
Layer 2 · Deterministic Verifier    deterministic rule validation (species/MLST/serotype/AMR/consensus)
  ↓
Layer 3 · AI interpretation         Skills knowledge base (interpret-results)
```

| Check category | Rule example | On failure |
|---|---|---|
| Species | `species_verdict` must contain "Salmonella" | FAIL |
| MLST | `mlst` field non-empty with an ST number | WARN |
| Serotype | `serotype.sistr` non-empty | WARN |
| AMR | Key genes (CTX-M/NDM/KPC/mcr-1) trigger review | NEEDS_REVIEW |

See [Deterministic Verifier](gom.en.md) and `src/hermes_bacmap/deterministic_verifier.py`.

## Core Python Modules

| Module | Lines | Responsibility |
|---|---|---|
| `tools/` | 2400+ | 29 Hermes tool handlers (seq / cli / pipeline / services + table-driven registry) |
| `genome_object_service.py` | 667 | GOM: SQLite CRUD + versioning + events + files + FTS5 |
| `schemas.py` | 950+ | JSON Schema definitions for 29 tools |
| `genome_annotator.py` | 280 | Genome annotation (pyrodigal + Prokka DBs) |
| `engine/` | 1121 | Algorithm abstraction layer (8 files) |
| `gene_scanner.py` | 546 | General-purpose gene scanning engine (delegates to engine.SequenceMatcher) |
| `shigella_serotyper.py` | 231 | Shigella serotyping (58 serotypes) |
| `deterministic_verifier.py` | 216 | Four-layer deterministic rule verification |
| `species_identifier.py` | 122 | Five-gene merged species identification |
| `ecoh_serotyper.py` | 134 | E. coli O:H serotyping |
| `__init__.py` | 28 | Plugin registration (table-driven, 24 tools + 4 skills) |

## Project Directory

```
hermes-bacmap/
├── src/hermes_bacmap/            Hermes plugin Python package
│   ├── engine/                   Algorithm abstraction layer (8 files, 800 lines)
│   ├── tools/                    Tool handler package (seq / cli / pipeline / services + registry)
│   ├── pathogen_registry.py      Pathogen registry (pathogens.yaml table-driven)
│   ├── schemas.py                Tool JSON Schemas
│   ├── genome_object_service.py  GOM
│   ├── deterministic_verifier.py Verification
│   └── ...
├── workflows/bacmap/             Snakemake pipeline
│   ├── Snakefile                 Main entry
│   ├── rules/                    10 .smk files (24 rules)
│   └── scripts/                  collect_summary / SNP matrix
├── scripts/                      Orchestration scripts (run_analysis / ingest / report)
├── skills/                       4 Hermes Skills
├── tests/                        1051 tests
├── data/reference/               13 reference databases
├── web/                          FastAPI Web UI
├── pixi.toml                     Bioinformatics tool dependencies
└── pyproject.toml                Python dependencies
```

Go deeper into each layer:

- [Engine layer](engine.en.md) — SequenceMatcher / ReadMapper / Hit / Registry
- [GOM data model](gom.en.md) — SQLite schema, versioning, event stream
- [Snakemake pipeline](pipeline.en.md) — 25 rules, DAG, species routing, SNP workflow
- [Skills system](skills.en.md) — 4 skills, three-layer progressive loading, bio-router decision tree
