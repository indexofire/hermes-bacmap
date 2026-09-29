# hermes-bacmap

**[简体中文](README.zh-CN.md)** | English

AI-native pathogen genome analysis platform — a plugin for the [Hermes Agent](https://github.com/NousResearch/hermes-agent).

From raw Illumina reads to species identification, serotyping, MLST, AMR/virulence profiling,
SNP phylogeny, cgMLST trace-back, and AI-driven outbreak investigation — every result recorded
in an auditable Genome Object Model (GOM) evidence chain with human review gates.

## Quick Start

1. Install [Hermes](https://hermes-agent.nousresearch.com/) following the [Hermes Agent](https://hermes-agent.nousresearch.com/) instructions.

2. Clone the repository and install the bioinformatics environment

```bash
git clone https://github.com/indexofire/hermes-bacmap.git
cd hermes-bacmap
pixi install
```

3. Install the plugin into Hermes

```bash
# Install into Hermes' Python environment (auto-registers entry-point + deps)
pip install -e . --python ~/.hermes/hermes-agent/venv/bin/python

# Enable the plugin
hermes plugins enable hermes_bacmap
```

4. (Optional) Deploy identification databases (interactive ANI / sourmash / GTDB-Tk tier selection)

```bash
pixi run setup
```

5. Start Hermes

Once the `hermes agent` is running, interact with it and let the AI analyze foodborne pathogen genomes for you.

```bash
hermes chat
```

---

## Development Environment

```bash
# 1. Bioinformatics environment (pixi: all runtime dependencies + Python libs)
pixi install

# 2. Start the Hermes Agent
hermes chat
```

Production users only need `pixi install`. Developers additionally run:
```bash
# 3. Python dev tools (uv: pytest / ruff / mypy only)
uv venv --python 3.12
uv pip install -e ".[dev]"
```

Full feature documentation: **[docs/features.md](docs/features.md)** ·
Environment setup details: **[docs/installation/environment.md](docs/installation/environment.md)**

## Supported Pathogens (v0.5.1: 34 registered species, 30 enabled + 4 high-consequence disabled by default)

**Fully validated pathogens (4)** — complete species ID / serotype / MLST / AMR / SNP pipelines verified against gold standards:

| Pathogen | Species ID | Serotype | MLST | AMR/Virulence | SNP/Phylogeny | Status |
|---|---|---|---|---|---|---|
| **Salmonella** | invA (marker) / ANI / GTDB-Tk | SISTR | gmlst (salmonella_2) | gapit (CARD/VFDB/PlasmidFinder) | bwa+bcftools+iqtree | ✅ |
| **DEC** (E. coli) | uidA (marker) / ANI / GTDB-Tk | ecoh_serotyper | gmlst | gapit | bwa+bcftools+iqtree | ✅ |
| **Shigella / EIEC** | ipaH (marker) / ANI / GTDB-Tk | shigella_serotyper (58) | gmlst | gapit | bwa+bcftools+iqtree | ✅ |
| **V. parahaemolyticus** | toxR+tlh (marker) / ANI / GTDB-Tk | VpaSerotyper | gmlst | gapit | bwa+bcftools+iqtree | ✅ |

**Extended species identification (30 enabled)** — multigene markers (80 sequences / 38 rules)
+ three ANI tiers (panel skani / mash_refseq / GTDB-Tk) + 7-method consensus arbitration,
covering common foodborne and opportunistic pathogens: Salmonella, E. coli, Shigella,
Vibrio (cholerae / parahaemolyticus / vulnificus), Listeria, S. aureus, S. pneumoniae,
S. pyogenes, K. pneumoniae, P. aeruginosa, A. baumannii, C. difficile, C. jejuni,
H. pylori, L. pneumophila, M. pneumoniae, N. meningitidis, B. cereus, and more
(full list in `src/hermes_bacmap/pathogens.yaml` and [docs/pathogens/](docs/pathogens/));
anthrax and 3 other high-consequence pathogens are registered but disabled by default.
Typing extensions: V. cholerae toxigenicity, L. monocytogenes serogroup,
C. difficile toxin type, B. cereus enterotoxin type.

## Agent Discovery Stack (new in v0.5.1)

Beyond fixed pipelines, the AI agent can mine your own data and evolve the platform:

- **Discovery** — MMseqs2 pan-genome clustering + DuckDB federated analytics +
  Fisher-exact differential enrichment (`bio_pangenome`, `bio_analytics_query`,
  `bio_differential_genes`)
- **Verification** — Europe PMC literature search + NCBI Pathogen Detection global
  surveillance comparison (`bio_lit_search`, `bio_ncbi_pathogen`)
- **Registration** — validated novel markers enter `marker_rules.yaml` and custom
  gapit screening databases atomically (`bio_marker_register`, `bio_db_build`)
- **L2 sandbox** — session-persistent Python execution, GOM read-only SQL, quick
  plotting (`bio_sandbox_exec`, `bio_sql_query`, `bio_plot`); sandbox outputs enter
  reports only after human sign-off
- **Numeric provenance guard** — every number in an AI report must trace back to
  GOM/tool evidence (orphan-claim detection)

## Core Modules

| Module | Lines | Function |
|---|---|---|
| `tools/` | 2700 | 39 Hermes tool handlers (seq / cli / pipeline / services / discovery / connectors / sandbox / curation packages, table-driven registry) |
| `schemas.py` | 1180 | 39 tool JSON schemas |
| `services/genome_object_service.py` | 749 | GOM (SQLite + versioning + events + file artifacts + FTS5 search) |
| `engine/` | 1230 | Algorithm abstraction (SequenceMatcher + ReadMapper + Hit; swappable backends: blast / minimap2 / kma / kmer / skani / mmseqs2) |
| `analysis/genome_annotator.py` | 280 | Genome annotation (pyrodigal + Prokka DBs, pure Python) |
| `analysis/pangenome.py` | 200 | Pan-genome discovery (mmseqs2 easy-linclust → cluster×sample presence/absence matrix, Parquet) |
| `analysis/analytics.py` | 310 | DuckDB federated analytics (zero-index queries over gapit TSVs/annotations/pan-genome + Fisher-exact enrichment) |
| `analysis/provenance.py` | 160 | Numeric provenance guard (orphan-claim detection for AI reports) |
| `analysis/sandbox.py` | 130 | L2 sandbox executor (subprocess + session variables + audit trail) |
| `analysis/plotting.py` | 110 | Quick plotting (bar/line/scatter/hist/heatmap, matplotlib Agg) |
| `analysis/gene_scanner.py` | 545 | Gene screening engine (delegates to engine.SequenceMatcher) |
| `analysis/nli_reflector.py` | 413 | Layer-3 NLI Reflector (atomic claim entailment/contradiction + audit events) |
| `services/marker_registry.py` | 140 | Marker registration (atomic marker_rules.yaml updates + backup + idempotency) |
| `services/literature.py` | 90 | Literature connector (Europe PMC: PubMed + preprints, no API key) |
| `services/ncbi_pathogen.py` | 160 | NCBI Pathogen Detection connector (7M+ isolates + MicroBIGG-E elements, live-verified API) |
| `services/gapit_ops.py` | 75 | Custom gapit database builder (capability-evolution deployment) |
| `typing/shigella_serotyper.py` | 231 | Shigella serotyping (ported ShigATyper) |
| `typing/vpa_serotyper_engine.py` | 450 | V. parahaemolyticus O/K serotyping (ported vpautils) |
| `analysis/deterministic_verifier.py` | 222 | Deterministic rule verification (species/MLST/serotype/AMR) |
| `analysis/species_identifier.py` | 123 | Marker-gene species ID (invA/uidA/ipaH/toxR/tlh; GTDB-Tk standard mode in `analysis/taxonomic_validator.py`) |
| `typing/ecoh_serotyper.py` | 134 | E. coli O:H serotyping (delegates to gene_scanner) |

> Paths are relative to `src/hermes_bacmap/`. Also `services/strain_index.py` (strain retrieval + FTS5),
> `analysis/cgmlst_*.py` (cgMLST trace-back projection/distances), `analysis/failure_diagnostics.py`
> (9 failure-mode diagnosis), and more — see [docs/features.md](docs/features.md).

## Project Structure

```
hermes-bacmap/
├── src/hermes_bacmap/           Hermes plugin Python package
│   ├── __init__.py             plugin registration (39 table-driven tools + skill autodiscovery)
│   ├── schemas.py              39 tool JSON schemas
│   ├── tools/                  tool handlers (seq / cli / pipeline / services + table-driven registry)
│   ├── engine/                 algorithm abstraction (SequenceMatcher / ReadMapper + swappable backends)
│   ├── analysis/               domain analysis (species ID / gene scanning / annotation / verification / cgMLST / NLI / diagnostics)
│   ├── typing/                 serotyping modules (ecoh / shigella / vpa)
│   ├── services/               GOM + strain index / strain metadata / lab results
│   └── skills/                 7 Hermes skills (packaged with the wheel)
├── workflows/bacmap/           Snakemake pipeline
│   ├── Snakefile               main entry (per-sample + cohort DAG)
│   ├── config/                 configuration + sample sheets
│   ├── rules/                  12 rule files (32 rules: 28 regular + 4 cgMLST cohort-gated; + `rule all` = 33)
│   └── scripts/                collect_summary + SNP/cgMLST cohort scripts + pathotype
├── scripts/                    orchestration scripts (run_analysis / ingest_results / generate_report / validation / ...)
├── web/                        FastAPI web UI (app.py + single-page template, X-API-Key auth)
├── tests/                      tests (1711 tests)
├── data/reference/             reference databases (8 categories: amr / annotation / genomes / plasmid / serotype / species / virulence / vpa_serotype)
├── docs/                       mkdocs documentation site (bilingual: zh + en)
├── mkdocs.yml                  docs site navigation (i18n)
├── pixi.toml                   bioinformatics tool dependencies
├── pyproject.toml              Python dependencies (MIT license)
└── project.md                  development plan (zh)
```

## Environment Architecture

| Tool | Manages | Notes |
|------|---------|-------|
| **pixi** | bioinformatics CLIs + Python runtime | fastp, Shovill, blast, bwa, samtools, bcftools, seqkit, iqtree, pyrodigal, snakemake, gmlst, mash, skani, kraken2, bracken, mmseqs2, duckdb, sourmash |
| **uv** (optional) | Python dev tools | pytest, ruff, mypy (developers only) |
| **Hermes Agent** | LLM orchestration | API-key mode (GLM via Z.AI, model-agnostic) |

## Daily Development

```bash
# Run tests
uv run pytest -v

# Lint
uv run ruff check src/ tests/

# Analyze one sample
python scripts/run_analysis.py --sample SAM-TYP-001

# Analyze all samples
python scripts/run_analysis.py --all

# Ingest into GOM
python scripts/ingest_results.py --all

# Generate reports
python scripts/generate_report.py --all
```

## Talking to Hermes

```bash
hermes chat
> list all samples
> analyze SAM-DEC-012
> is ipaH positive in SAM-SHI-013?
> compare SAM-SHI-013 and SAM-EIEC-014
> investigate this outbreak group against the background strains
> generate the report for SAM-TYP-001
```

## Deploying to Hermes

```bash
# 1. Install plugin + deps into the Hermes venv (entry-point auto-registers)
pip install -e . --python ~/.hermes/hermes-agent/venv/bin/python

# 2. Enable the plugin
hermes plugins enable hermes_bacmap

# 3. If databases live outside the default location, set env vars
export BACMAP_DATA_DIR=/path/to/hermes-bacmap/data
```

Full guide: **[docs/installation/quick-start.md](docs/installation/quick-start.md)**.

## License

Released under the [MIT License](LICENSE).
