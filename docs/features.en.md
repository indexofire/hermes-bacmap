# Hermes-bacmap Features

> **Version**: V0.7 (2026-09-07)
> **Status** (v0.5.1): 39 Hermes tools · 33 Snakemake rules (28 regular + 4 cgMLST cohort-gated + `rule all`) · 1711 tests · 7 skills
> · engine abstraction layer · discovery stack (MMseqs2+DuckDB) · external connectors · L2 sandbox · capability-evolution registry
> **Datasets**: strain metadata + wet-lab results · cgMLST trace-back · 12-strain dataset (11 analyzed, 9 verified via the §12.3 harness)
> Test accounting: 1415 = V0.7 final state (P0 +13 / P1 +16 / P2 +8 / P3 +2: web events endpoint; see CHANGELOG for details)

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Core Python Modules](#2-core-python-modules)
3. [Hermes Tools (25)](#3-hermes-tools-25)
4. [Snakemake Pipeline (30 rules)](#4-snakemake-pipeline-30-rules)
5. [Genome Object Model (GOM)](#5-genome-object-model-gom)
6. [Species Identification System](#6-species-identification-system)
7. [Serotyping](#7-serotyping)
8. [AMR / Virulence / Plasmid Detection](#8-amr--virulence--plasmid-detection)
9. [SNP Phylogenetic Analysis](#9-snp-phylogenetic-analysis)
10. [Cohort Analysis and GOM Ingestion](#10-cohort-analysis-and-gom-ingestion)
11. [Natural-Language Sample Search](#11-natural-language-sample-search)
12. [Deterministic Verifier](#12-deterministic-verifier)
13. [Bioinformatics Knowledge Skills](#13-bioinformatics-knowledge-skills)
14. [Orchestration Scripts](#14-orchestration-scripts)
15. [CI/CD and Quality Assurance](#15-cicd-and-quality-assurance)
16. [Reference Databases](#16-reference-databases)
17. [Gold Standard Validation Dataset](#17-gold-standard-validation-dataset)

---

## 1. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│               User (natural language, zh/en)                 │
└──────────────────────────┬───────────────────────────────────┘
                           │
                ┌─────────▼───────────┐
                │    Hermes Agent     │  GLM-5.2 via Z.AI API
                │ (LLM orchestration) │  16 tools + 3 skills
                └─────────┬───────────┘
                           │
        ┌─────────────────┼─────────────────────┐
        │                 │                     │
┌───────▼───────────┐ ┌───▼───────────────┐ ┌───▼──────────────┐
│ L1 fixed          │ │ L2 deterministic  │ │ L3 AI            │
│ pipelines         │ │ verification      │ │ interpretation   │
│ Snakemake DAG     │ │ Verifier          │ │ Skills + search  │
│ 30 rules          │ │ 21 tests          │ │ FTS5 + KB        │
└───────┬───────────┘ └───┬───────────────┘ └───┬──────────────┘
        │                 │                     │
        └─────────────────┼─────────────────────┘
                          │
                ┌─────────▼───────────┐
                │   Genome Object     │  SQLite + WAL + FTS5
                │   Model (GOM)       │  4 tables, 5 indexes
                └─────────┬───────────┘
                          │
                ┌─────────▼───────────┐
                │  Local filesystem   │  FASTQ / FASTA / VCF / BAM
                └─────────────────────┘
```

### Technology Choices

| Layer | Technology | Rationale |
|---|---|---|
| LLM inference | API-key mode (GLM-5.2) | No GPU required, simple deployment |
| Workflow engine | Snakemake 7.32 | Python DSL; AI can generate/modify rules |
| Metadata storage | SQLite + WAL + FTS5 | Zero ops, single file, Hermes-compatible |
| File storage | Local filesystem | Simple and reliable; migratable to MinIO in V1.0+ |
| Package management | uv (Python) + pixi (bioinformatics tools) | Separates Python dependencies from bioinformatics CLIs |

---

## 2. Core Python Modules

| Module | Lines | Responsibility |
|---|---|---|
| `tools/` | 2115 | 26 Hermes tool handlers (7-file package: seq / cli / pipeline / services + registry) |
| `genome_object_service.py` | 667 | GOM: SQLite CRUD + versioning + events + file artifacts + FTS5 search |
| `schemas.py` | 893 | JSON Schema definitions for the 26 tools |
| `genome_annotator.py` | 280 | Genome annotation in Python (pyrodigal + Prokka DBs, replaces the Prokka CLI) |
| `engine/` | 1121 | Algorithm abstraction layer: SequenceMatcher + ReadMapper + Hit + Registry |
| `gene_scanner.py` | 546 | Generic gene-scanning engine (delegates to engine.SequenceMatcher) |
| `shigella_serotyper.py` | 231 | Shigella serotype prediction (ported ShigATyper, 58 serotypes) |
| `deterministic_verifier.py` | 216 | Deterministic rule verification (four-layer checks: species/MLST/serotype/AMR) |
| `__init__.py` | 28 | Plugin registration (table-driven, 26 tools + 4 skills autodiscovery) |
| `species_identifier.py` | 122 | Unified species identification (five genes invA/uidA/ipaH/toxR/tlh merged into 1 BLAST call) |
| `ecoh_serotyper.py` | 134 | E. coli O:H serotyping (delegates to gene_scanner) |

---

# 3. Hermes Tools (26)

### 3.1 Low-Level Bioinformatics Tools (8)

| Tool | Function | Underlying tool |
|---|---|---|
| `bio_seq_stats` | FASTA/FASTQ/GenBank statistics (N50, GC, length distribution, quality distribution) | Biopython |
| `bio_seq_ops` | Sequence operations (reverse complement, translation, GC-skew, motif, ORF, restriction sites, k-mer) | Biopython |
| `bio_fastq_qc` | FASTQ QC + adapter detection | fastp |
| `bio_seq_convert` | Format conversion (FASTA/FASTQ/GenBank/EMBL and 9 formats in total) | Biopython |
| `bio_blast` | Local + remote (NCBI) BLAST | blastn/blastp/blastx |
| `bio_align` | Sequence alignment (BWA-MEM / minimap2 / STAR) | bwa, minimap2 |
| `bio_samtools` | SAM/BAM operations (9 subcommands: index/sort/flagstat/view/depth/faidx/mpileup/consensus/fixmate) | samtools |
| `bio_variant` | Variant calling (mpileup_call/filter/query/annotate/consensus) | bcftools |

### 3.2 High-Level Analysis Tools (18)

| Tool | Function | Input | Output |
|---|---|---|---|
| `bio_analyze_pathogen` | Triggers the full Snakemake pipeline (cross-pathogen auto-routing) | sample_id | summary.json |
| `bio_get_result` | Compact per-sample result summary | sample_id | JSON (species/mlst/serotype/amr) |
| `bio_verify_result` | Runs the Deterministic Verifier | sample_id | VerificationResult |
| `bio_generate_report` | Generates HTML reports (single sample / all / cohort) | sample_id or --cohort | HTML file |
| `bio_list_samples` | Lists all samples with analysis status | none | sample status list |
| `bio_gene_scan` | Multi-database gene scanning (CARD/VFDB/ecoh/plasmidfinder/resfinder etc., 9 databases) | contigs path + database name | JSON (gene list + identity + coverage) |
| `bio_snp_tree` | Cohort-level phylogenetic tree + distance matrix | none | Newick + pairwise distances |
| `bio_cgmlst` | cgMLST trace-back: nearest reference strain + per-species threshold verdict (outbreak/related/unrelated) | sample_id | ProjectionResult JSON |
| `bio_search_samples` | Natural-language sample search (FTS5 + field weighting) | query terms | matched sample list (with matched field + relevance score) |
| `bio_review_flags` | Reads back Layer 3 human-review flags (nli_reflected audit event list) | limit | flagged samples + contradiction rate + contradicting-claim details |
| `bio_annotate` | Genome annotation (pyrodigal CDS + Prokka DBs blastp) | contigs path | annotation JSON |
| `bio_validate_taxonomy` | Species identification (dual mode: marker genes / GTDB-Tk) | sample_id, mode | completeness / contamination / gtdb_taxonomy |
| `bio_diagnose` | Diagnoses pipeline failures (parses Snakemake logs) | log_path or stderr_text | error type / root cause / fix command |
| `bio_vpa_serotype` | V. parahaemolyticus O/K serotype prediction | contigs path | serotype + confidence + coverage |
| `bio_add_metadata` | Enter/update strain background metadata | sample_id + fields | metadata record |
| `bio_query_metadata` | Query strain background metadata (epidemiological information) | filter conditions | matched records |
| `bio_add_lab_result` | Enter wet-lab results (AST/serology/biochemistry/PCR) | sample_id + results | lab record |
| `bio_query_lab_results` | Query wet-lab results | filter conditions | matched records |

### bio_search_samples weighting strategy

| Match field | Score | Notes |
|---|---|---|
| serotype exact match | 10 | e.g. search "Typhimurium" → sistr=Typhimurium |
| MLST ST match | 10 | e.g. search "ST2" → mlst_st=2 |
| AMR gene-name match | 9 | e.g. search "CRP" → amr genes contains CRP |
| MLST raw text | 8 | any field match in the TSV |
| plasmid match | 7 | PlasmidFinder gene name |
| strain_id match | 6 | sample identifier |
| organism match | 5 | species name |
| FTS5 full-text match | 1 | degraded fallback |

---

## 4. Snakemake Pipeline (30 rules)

### 4.1 DAG Overview

```
rule all
  ├── {sample}/report/{sample}_summary.json  (per-sample, ×10)
  │     └── report_summary (collect_summary.py)
  │           ├── qc_fastp → {sample}_fastp.json
  │           ├── assembly_shovill → contigs.fasta
  │           │     └── assembly_stats → assembly_stats.tsv
  │           ├── species_identify → species_id.json
  │           ├── typing_mlst → mlst.tsv
  │           ├── typing_sistr → sistr.json
  │           ├── amr_abricate_vfdb → abricate_vfdb.tsv
  │           ├── amr_abricate_card → abricate_card.tsv
  │           ├── amr_abricate_plasmidfinder → abricate_plasmidfinder.tsv
  │           ├── dec_ecoh_serotype → ecoh_serotype.json
  │           ├── dec_pathotype → pathotype.tsv
  │           └── shigella_serotype → shigella_serotype.json
  │
  └── snp/snp_summary.json  (cohort-level)
        └── snp_summary (generate_snp_summary.py)
              └── phylo_tree → core.treefile + core.iqtree
                    └── snp_matrix → core_snps.fasta
                          └── joint_variant_calling → joint.vcf.gz
                                └── snp_calling (×7) → snps.bam
```

### 4.2 Rule Inventory

| Module file | Rule | Description |
|---|---|---|
| `qc.smk` | `qc_fastp` | fastp QC + adapter trimming |
| `assembly.smk` | `assembly_shovill` | Shovill assembly (SPAdes + read correction) |
| | `assembly_stats` | seqkit stats |
| `species.smk` | `species_identify` | five-gene species identification (1 BLAST call) |
| `typing_amr.smk` | `typing_mlst` | gmlst (salmonella_2 scheme) |
| | `typing_sistr` | SISTR serotyping + cgMLST |
| | `amr_abricate_vfdb` | virulence gene scanning |
| | `amr_abricate_card` | AMR gene scanning |
| | `amr_abricate_plasmidfinder` | plasmid replicon detection |
| | `amr_amrfinderplus` | NCBI AMRFinderPlus (--organism mapped by species) |
| `dec_shigella.smk` | `dec_ecoh_serotype` | E. coli O:H serotype |
| | `dec_pathotype` | DEC pathotype calling (STEC/EPEC/EIEC/ETEC/EAEC) |
| | `shigella_serotype` | Shigella serotyping |
| `vpara.smk` | `vpara_targets` | V. parahaemolyticus species identification (toxR + tlh) |
| | `vpara_virulence` | virulence gene detection (tdh/trh/tlh) |
| | `vpara_serotype` | V. parahaemolyticus O/K serotyping (native Python) |
| `annotation.smk` | `genome_annotation` | pyrodigal CDS + Prokka DBs blastp annotation |
| `taxonomy.smk` | `taxonomy_validation` | GTDB-Tk standard-mode validation (graceful degradation when unavailable) |
| `cgmlst.smk` | `typing_cgmlst` | cgMLST typing (per-sample, EnteroBase schemes) |
| | `cgmlst_cohort_profiles` ⭑ | cohort multi-sample profile merging |
| | `cgmlst_distance_matrix` ⭑ | allelic distance matrix (Hamming) |
| | `cgmlst_mst` ⭑ | minimum spanning tree (MST) |
| | `cgmlst_summary` ⭑ | cohort summary JSON |
| `snp.smk` | `snp_calling` | per-sample BWA alignment to the reference genome |
| | `joint_variant_calling` | multi-sample joint variant calling (bcftools mpileup + call) |
| | `snp_matrix` | whole-genome SNP matrix generation (FASTA, N-filled missing) |
| | `phylo_tree` | IQ-TREE maximum-likelihood tree (GTR, UFBoot 1000) |
| | `snp_summary` | distance matrix + Newick summary JSON |
| `report.smk` | `report_summary` | collect_summary.py aggregates all steps |
| `Snakefile` | `all` | main target (per-sample summaries + cohort SNP + cgMLST cohort) |

> ⭑ = cohort-gated rules; they enter the DAG only when `cgmlst.run_cgmlst_cohort: true` in `config.yaml`.

---

## 5. Genome Object Model (GOM)

### 5.1 SQLite Table Schema

```sql
-- 核心对象表（所有类型共用，JSON 列存储具体内容）
CREATE TABLE genome_objects (
    object_id TEXT NOT NULL,           -- UUID v4
    object_type TEXT NOT NULL,          -- sample|analysis|report|...
    version INTEGER NOT NULL,           -- 单调递增，从 1 开始
    schema_version TEXT NOT NULL,       -- semver "0.1.0"
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    payload_json TEXT NOT NULL,         -- 所有分析结果存于此 JSON
    organism TEXT,                      -- 索引字段
    strain_id TEXT,                     -- 索引字段
    pipeline_version TEXT,              -- ANALYSIS 必填（证据链）
    database_signature TEXT,
    PRIMARY KEY (object_id, version)    -- 复合主键 → 版本化 + 不可变
);

-- 全文搜索虚拟表
CREATE VIRTUAL TABLE genome_objects_fts USING fts5(
    object_type, organism, strain_id, payload_text
);

-- 事件流（Event First 原则）
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    event_type TEXT NOT NULL,           -- uploaded|qc_finished|...|snp_finished
    event_payload TEXT NOT NULL,        -- JSON
    timestamp TEXT NOT NULL
);

-- 文件产物引用（大文件留在文件系统，DB 存路径 + SHA256）
CREATE TABLE file_artifacts (
    artifact_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,               -- 64 字符 hex，写入时实时校验
    size_bytes INTEGER NOT NULL
);
```

### 5.2 Core Design Principles

| Principle | Implementation |
|---|---|
| **Immutable** | `delete()` always raises; duplicate (object_id, version) raises |
| **Version First** | `create_new_version()` automatically inherits metadata, version number +1 |
| **Event First** | every lifecycle stage logs an event (uploaded → qc → assembly → ... → snp_finished) |
| **Triple evidence chain** | ANALYSIS objects must carry (strain_id, pipeline_version, database_versions) |
| **JSON-in-SQLite** | no per-type tables; all results go into payload_json, schema-less flexibility |

### 5.3 GOS Class Interface

| Category | Method | Description |
|---|---|---|
| CRUD | `create(obj)` | create (duplicates raise GOMImmutableError) |
| | `read(object_id, version)` | read a specific version |
| | `list_by_type(object_type)` | list latest versions |
| | `list_by_organism(organism)` | filter by organism |
| | `search(query)` | FTS5 full-text search |
| Version | `create_new_version(object_id, payload)` | create a new version |
| | `get_latest_version(object_id)` | get the latest version number |
| | `list_versions(object_id)` | list all versions |
| File | `register_file_artifact(...)` | register a file (with live SHA256 verification) |
| | `list_file_artifacts(object_id)` | list file artifacts |
| Event | `log_event(object_id, type, payload)` | log an event |
| | `list_events(object_id, since)` | list events (supports time filtering) |

---

## 6. Species Identification System

### Design

The 5 species-specific target genes are merged into 1 FASTA database (`species/markers.fasta`); a single BLAST call completes all species identification.

| Target gene | Target species | Reference sequence | Length |
|---|---|---|---|
| invA | Salmonella spp. | M90846.1 | 2,176 bp |
| uidA | E. coli / DEC | NC_000913.3 | 1,190 bp |
| ipaH | Shigella / EIEC | NC_004337.2 | 1,827 bp |
| toxR | V. parahaemolyticus | BA000031.2 | 643 bp |
| tlh | V. parahaemolyticus | M36437.1 | 1,302 bp |

### Routing Logic

```
contigs.fasta
    ↓ BLAST vs species/markers.fasta (1 call)
    ↓
    invA positive → Salmonella → Salmonella typing pipeline
    uidA positive → E. coli/DEC → DEC pipeline (ecoh_serotyper + pathotype)
    ipaH positive → Shigella/EIEC → Shigella pipeline (shigella_serotyper)
    toxR+tlh positive → V. parahaemolyticus → V.para pipeline
```

### Validation Results

All 10 gold-standard strains were correctly identified (sensitivity 100%, specificity 100%):
- 7 Salmonella strains → invA positive ✅
- 1 E. coli (K-12 MG1655) → uidA positive, invA negative ✅
- 1 Shigella → ipaH positive ✅
- 1 EIEC → ipaH positive ✅

> 2026-09 V0.7 expansion: after adding SAM-MCR-010 (invA ✅) and re-running SAM-ECO-011 (uidA ✅),
> the dataset reached **12 strains** (11 analyzed), 9 re-checked via the §12.3 verification
> harness — see docs/validation-report.md for the latest metrics.

---

## 7. Serotyping

### Three-Way Routing

| Species | Tool | Database | Output |
|---|---|---|---|
| Salmonella | SISTR | salmonella_atdb | serovar + serogroup + O/H antigen |
| DEC / EIEC | ecoh_serotyper (Python) | serotype/ecoh.fasta (753KB, 597 seqs) | O:H serotype + interpretation |
| Shigella | shigella_serotyper (Python) | serotype/shigella.fasta (122KB, 95 seqs) | species + serotype (58 types) |

### ecoh_serotyper

- 121 lines of pure Python; BLAST logic delegated to gene_scanner (zero code duplication)
- The database contains 597 O/H antigen sequences (vs ECTyper's 944MB MASH DB)
- Output: O type + H type + full serotype (e.g. "O157:H7")

### shigella_serotyper

- 207 lines, ported from ShigATyper (CFSAN)
- Supports 58 serotypes:
  - S. flexneri: 1a, 1b, 1c, 1d, 2a, 2b, 3a, 3b, 4a, 4b, 5a, 6, 7a, 7b, Y, Yv
  - S. sonnei: I, II
  - S. dysenteriae: 1-15
  - S. boydii: 1-20

### collect_summary.py serotype routing logic

```python
if "Shigella" in species and serotype != "Undetermined":
    primary_serotype = shigella_serotype       # shigella_serotyper
elif ecoh_serotype != "-:-":
    primary_serotype = ecoh_serotype           # ecoh_serotyper (DEC/EIEC)
else:
    primary_serotype = sistr_serovar           # SISTR (Salmonella)
```

---

## 8. AMR / Virulence / Plasmid Detection

### Databases

| Database | File size | Sequences | Detects |
|---|---|---|---|
| CARD | 6.5 MB | ~5,000 | AMR genes |
| VFDB | 6.3 MB | ~4,000 | virulence factors |
| PlasmidFinder | 437 KB | ~400 | plasmid replicons |

### Integration

Invokes `abricate` via Snakemake rules (3 parallel rules):
```
amr_abricate_vfdb:        abricate --db vfdb {contigs} → abricate_vfdb.tsv
amr_abricate_card:        abricate --db card {contigs} → abricate_card.tsv
amr_abricate_plasmidfinder: abricate --db plasmidfinder {contigs} → abricate_plasmidfinder.tsv
```

### gene_scanner generic engine

The `bio_gene_scan` Hermes tool provides runtime dynamic scanning across 9 databases:
`card, vfdb, ecoh, plasmidfinder, resfinder, ncbi, megares, victors, ecoli_vf`

It is driven by `gene_scanner.py` (400 lines), which checks BLAST return codes (non-zero raises RuntimeError, preventing silent false negatives).

---

## 9. SNP Phylogenetic Analysis

### Pipeline (5 steps)

```
Step 1: snp_calling (per strain)
  raw FASTQ → bwa mem (vs LT2 reference genome) → samtools sort → BAM

Step 2: joint_variant_calling (multi-sample joint)
  7 BAMs → bcftools mpileup (joint) → bcftools call → joint VCF
  ※ key point: joint calling guarantees cross-sample genotype consistency

Step 3: snp_matrix (whole-genome SNP matrix)
  joint VCF → Python parsing → FASTA alignment
  strategy: whole-genome mode (all variant sites retained, missing data filled with N)

Step 4: phylo_tree (phylogenetic tree)
  FASTA → IQ-TREE -m GTR -bb 1000 -alrt 1000
  output: Newick treefile + IQ-TREE report

Step 5: snp_summary (distance matrix)
  treefile + FASTA → JSON (Newick + pairwise distances + statistics)
```

### Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Variant-calling strategy | **Joint calling** (not per-sample calling then merge) | avoids cross-sample genotype inconsistency |
| Matrix strategy | **Whole-genome** (not strict core) | retains all variant sites, N fills missing data (4.7%), no signal loss |
| Alignment format | **FASTA** (not PHYLIP) | no 10-character name truncation limit |
| Reference genome | NC_003197.2 (S. Typhi LT2, 4.8Mb) | chromosome only, plasmids excluded |

### Validation Results (7 Salmonella strains)

| Metric | Value |
|---|---|
| SNP sites | 122,598 |
| Missing rate | 4.7% |
| Parsimony-informative sites | 55,437 |
| Bootstrap support | all internal branches ≥ 92% |

**Topology correctness validation**:
- The two Typhimurium strains (TYP-001 + TYP-002) cluster together, SNP distance = 1,666 ✅
- The two Newport strains (ENT-003 + NEW-006) cluster together ✅
- Typhi (CTX-008) has the longest branch (0.677) ✅

---

## 10. Cohort Analysis and GOM Ingestion

### Cohort Object Design

SNP analysis produces a **multi-sample (cohort-level)** result that cannot go into per-sample GOM objects. Solution:

```
创建 1 个 cohort-level ANALYSIS GenomeObject:
  strain_id = "cohort:salmonella-snp"   ← 去重键
  organism = "Salmonella enterica"
  payload = {
      "analysis_type": "snp_cohort",
      "samples": ["SAM-TYP-001", ...],   ← 7 个样本
      "tree_newick": "(SAM-TYP-001:0.005,...",
      "pairwise_distances": {"SAM-TYP-001|SAM-TYP-002": 1666, ...},
      "n_snp_sites": 122598,
      "missing_rate": 0.0467
  }
  pipeline_version = "snp-pipeline-v0.3"
```

### File Artifact Registration

| file_type | File | Description |
|---|---|---|
| snp_tree_newick | core.treefile | Newick tree file |
| snp_alignment | core_snps.fasta | SNP alignment sequences |
| iqtree_report | core.iqtree | full IQ-TREE report |
| joint_vcf | joint.vcf.gz | joint VCF |
| snp_summary | snp_summary.json | summary JSON |

### Sample Linking

Each sample's ANALYSIS object records an `snp_finished` event whose payload contains the cohort object_id reference:

```python
gos.log_event(sample_object_id, "snp_finished", {
    "cohort_object_id": cohort_oid,
    "strain_id": "SAM-TYP-001",
})
```

### Ingestion Commands

```bash
# 先入库所有单株结果
python scripts/ingest_results.py --all

# 再入库 SNP cohort
python scripts/ingest_results.py --snp
```

### Idempotency

Repeated ingestion with the same pipeline_version is skipped (`⏭️ 已存在 v1, skipped`).

---

## 11. Natural-Language Sample Search

### bio_search_samples tool

Users can query ingested sample results in natural language:

```
User: "Which samples are Typhimurium?"
→ bio_search_samples(query="Typhimurium")
→ returns 2 matches (score=10, serotype exact match)

User: "Which samples are ST19?"
→ bio_search_samples(query="ST19")
→ returns samples matching ST19 (score=10, MLST match)

User: "Which samples carry the CRP AMR gene?"
→ bio_search_samples(query="CRP")
→ returns all samples whose AMR genes contain CRP (score=9)
```

### Search Flow

```
1. Iterate over all ANALYSIS objects (excluding the cohort: prefix)
2. For each object, check whether payload fields match the query:
   - serotype.sistr → score 10
   - mlst ST number ("ST2" format supported) → score 10
   - AMR gene name → score 9
   - plasmid gene name → score 7
   - organism → score 5
   - strain_id → score 6
   - FTS5 full text → score 1 (degraded fallback)
3. Deduplicate (keep only the latest of multiple versions)
4. Sort by score descending, return the top 50
```

---

## 12. Deterministic Verifier

### Three-Layer Defense

```
LLM-generated results → Layer 1: JSON Schema validation → Layer 2: deterministic rule checks → Layer 3: AI interpretation
                                                                   ↑
                                                         Deterministic Verifier
```

### Layer 3 NLI Reflector (AI interpretation self-check, V0.7)

Triggered when `bio_verify_result` is passed `interpretation_text` (an LLM interpretation
draft): the text is decomposed into atomic claims (species/ST/serotype/AMR/virulence/plasmid,
Chinese and English + negated forms), each compared against Source-of-Truth facts
(entailed/contradicted/unverifiable); a contradiction rate above the threshold triggers
NEEDS_HUMAN_REVIEW. Contradiction details are stored as GOM `nli_reflected` audit events;
`bio_review_flags` reads them back (human-review closed loop), and reports include an
"AI interpretation self-check" section (inherited by PDF).

- Comparison semantics: ENTAILED iff (claim matches fact != negated form); gene identities
  normalized via `gene_identity.normalize_amr` (blaCTX-M-15 ≡ CTX-M-15, MCR-1.1 ≡ mcr-1);
  the rate denominator counts only text-extracted claims (corroborated backfill tallied
  separately as `corroborated_count`, preventing dilution)
- **The 0.1 threshold is a module constant** (`nli_types.DEFAULT_CONTRADICTION_THRESHOLD`):
  a defense-layer default rather than an analytical threshold, following the same precedent
  as Layer 2's `_CRITICAL_AMR_PATTERNS` (defense parameters change with code review);
  can be overridden per call via `reflect(threshold=...)`

### Verification Rules (4 categories)

| Check category | Rule | On failure |
|---|---|---|
| Species | species_verdict contains "Salmonella" | ❌ FAIL |
| MLST | mlst field non-empty with an ST number | ⚠️ WARN |
| Serotype | serotype.sistr non-empty | ⚠️ WARN |
| AMR | critical AMR genes (CTX-M/NDM/KPC/mcr-1) trigger human review | ⚠️ NEEDS_REVIEW |

### Code Interface

```python
from hermes_bacmap.analysis.deterministic_verifier import DeterministicVerifier

v = DeterministicVerifier()
result = v.verify_all(summary_dict)
# result.passed → bool
# result.checks → list[CheckResult]
# result.needs_human_review → bool
# result.failed_count → int
```

### Test Coverage

21 TDD tests cover all rule paths (positive + negative + edge cases).

---

## 13. Bioinformatics Knowledge Skills

| Skill | Lines | Purpose |
|---|---|---|
| `bio-router` | 87 lines | always-loaded skill router (decision tree + tool catalog + pathogen capability matrix) |
| `run-pipeline` | 95 lines + 5 references | cross-pathogen pipeline operation guide (QC→assembly→species→MLST→serotype→AMR→SNP→report) |
| `interpret-results` | 174 lines + 2 references | result-interpretation knowledge base (serotype/MLST/AMR/SNP distance/virulence gene clinical significance) |
| `bioinfo-analysis` | 91 lines | generic bioinformatics decision tree (FASTQ→QC, FASTA→stats, BAM→samtools) |

### run-pipeline pathogen-specific references (Tier 3 references)

| File | Content |
|---|---|
| `references/salmonella.md` | SISTR, invA, salmonella_2 MLST, SNP reference genome, common AMR genes |
| `references/dec-shigella.md` | ecoh_serotyper, shigella_serotyper (58 types), ipaH, DEC pathotype calling rules |
| `references/vpara.md` | toxR/tlh species identification, tdh/trh virulence detection, V.para capability status table |
| `references/pipeline-params.md` | Snakemake parameters, assembly quality thresholds, per-step time/RAM |
| `references/troubleshooting.md` | common errors + fix steps (lock, OOM, missing DB, etc.) |

### interpret-results content overview

| Section | Content |
|---|---|
| Salmonella serotypes | Kauffmann-White scheme interpretation; 6 clinically important serotypes; monophasic Typhimurium |
| E. coli/DEC | 5 pathotypes (STEC/EPEC/EIEC/ETEC/EAEC); Big Six non-O157; Shigella vs EIEC |
| MLST | clinical significance of ST19=Typhimurium, ST11=Enteritidis, ST131=ExPEC, etc. |
| AMR genes | β-lactamase tiers (carbapenemase > ESBL > AmpC > penicillinase); clinical severity grading |
| SNP distance | 0-5 SNPs=homologous transmission chain; 6-15=possibly related; >50=different lineages; caveats |
| Virulence genes | SPI-1/SPI-2 secretion systems; spv virulence plasmid; sop effector proteins |
| Reporting guide | 5 result-summary principles (species confirmation → actionable findings → unusual markers → context → limitations) |

### Registration Mechanism

`__init__.py` autodiscovers `skills/*/SKILL.md` and registers them with Hermes via `ctx.register_skill()`.

---

## 13.5 GBrain Knowledge-Brain Layer (replaces §8.3 RAG)

project.md §8.3 originally planned a three-tier RAG (vector store + knowledge graph + BM25).
Instead, [GBrain](https://github.com/garrytan/gbrain) (25.2K stars) is adopted as the
knowledge layer — zero in-house code.

### Architecture Division

```
User: "SAM-TYP-001 has blaCMY-2, what is the clinical significance?"
  │
  ├── hermes_bacmap (GOM/SQLite) → "SAM-TYP-001 detected blaCMY-2" (fact query)
  │
  └── GBrain (PGLite) → "blaCMY-2 is an AmpC β-lactamase..." (knowledge synthesis + citations)
```

| Layer | System | Answers | Technology |
|---|---|---|---|
| **Fact layer** | GOM (SQLite) | "What was detected in sample X?" | exact SQL queries, zero hallucination |
| **Knowledge layer** | GBrain (PGLite) | "What does it mean?" | hybrid search + synthesized answers + citations + gap analysis |

### GBrain Core Capabilities

| Capability | Description |
|---|---|
| **Synthesized answers** (`gbrain think`) | returns not a page list but a cited synthesized answer + gap analysis |
| **Self-wiring knowledge graph** | `[[wiki]]` references auto-create edges (zero LLM calls), multi-hop traversal supported |
| **Hybrid search** (`gbrain search`) | HNSW vectors + BM25 keywords + RRF fusion + reranker |
| **Cron nightly maintenance** | automatic deduplication, reference repair, scoring, contradiction discovery |
| **MCP integration** | 30+ tools, stdio/HTTP, native Hermes support |

### Installation and Configuration

```bash
# 1. 安装 Bun + GBrain
curl -fsSL https://bun.sh/install | bash
export PATH="$HOME/.bun/bin:$PATH"
git clone --depth 1 https://github.com/garrytan/gbrain.git ~/gbrain
cd ~/gbrain && bun install && bun link
ln -sf ~/gbrain/src/cli.ts ~/.bun/bin/gbrain

# 2. 初始化（本地 PGLite，2 秒）
gbrain init --pglite --no-embedding  # 延迟配置 embedding

# 3. 导入生信知识种子
gbrain import ~/repo/github/hermes-bacmap/skills/interpret-results/
gbrain import ~/repo/github/hermes-bacmap/skills/interpret-results/references/
gbrain import ~/repo/github/hermes-bacmap/skills/run-pipeline/references/

# 4. 配置本地 embedding（零成本）
ollama pull nomic-embed-text
gbrain init --force --pglite \
  --embedding-model ollama:nomic-embed-text \
  --embedding-dimensions 768
gbrain import ~/repo/github/hermes-bacmap/skills/  # 重新导入并生成向量

# 5. 连接 Hermes（MCP）
gbrain serve  # stdio MCP，Hermes 自动发现
```

### Embedding Model Options

| Provider | Model | Dimensions | Cost | Notes |
|---|---|---|---|---|
| **Ollama** (recommended) | nomic-embed-text | 768 | Free | GPU accelerated, ~300MB VRAM |
| **Ollama** | mxbai-embed-large | 1024 | Free | higher accuracy |
| **llama.cpp** | any GGUF | user-specified | Free | most flexible |
| OpenAI | text-embedding-3-small | 1536 | $0.02/1M | cloud |
| ZeroEntropy | zembed-1 | 2560 | $0.05/1M | GBrain default |

### Hermes Integration

GBrain connects at the **Hermes platform layer** (not the hermes-bacmap plugin layer):

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  gbrain:
    command: gbrain
    args: ["serve"]
```

After installation, **hermes-bacmap requires zero changes**. The LLM orchestrates naturally:
- `bio_search_samples` → query GOM facts
- `gbrain think` → query GBrain knowledge
- synthesize both results → complete interpretation

### Imported Knowledge Content (10 pages)

| Page | Source |
|---|---|
| interpret-results skill | serotype/MLST/AMR/SNP interpretation guide |
| amr-gene-reference | β-lactamase tiers + reporting language |
| snp-distance-thresholds | outbreak determination thresholds + tree-reading guide |
| salmonella | SISTR/invA/MLST/SNP reference |
| dec-shigella | ecoh/shigella_serotyper/pathotype |
| vpara | toxR/tlh/tdh/trh virulence detection |
| pipeline-params | parameters + quality thresholds + runtimes |
| troubleshooting | common errors + fix steps |

---

## 13.6 Strain Metadata + Wet-Lab Results System

### Three-Table Data Architecture

```
┌──────────────────────────────────────────────────────────┐
│              data/hermes_bacmap.sqlite                    │
│                                                          │
│  strain_metadata     lab_results        genome_objects    │
│  ┌──────────┐       ┌──────────┐      ┌──────────┐      │
│  │strain_id │──┐    │strain_id │──┐   │strain_id │      │
│  │patient_* │  │    │category  │  │   │payload   │      │
│  │isolation_│  │    │test_name │  │   │version   │      │
│  │province  │  │    │result    │  │   └──────────┘      │
│  │outbreak  │  │    │method    │  │                     │
│  │extra JSON│  │    │extra JSON│  │   events             │
│  └──────────┘  │    └──────────┘  │   file_artifacts     │
│       1        │       N          │       1              │
│                └───────┬──────────┘                      │
│                strain_id (JOIN hub)                       │
└──────────────────────────────────────────────────────────┘
```

| Table | Rows per strain | Change pattern | Stores |
|---|---|---|---|
| **strain_metadata** | 1 | written once, occasionally corrected | patient info / isolation info / outbreak association |
| **lab_results** | 0-50 | appendable | AST/serology/biochemistry/PCR lab results |
| **genome_objects** | 1+ | versioned (immutable) | bioinformatics analysis results |

### strain_metadata (strain background information)

**27 core columns + extra JSON extension column**

| Category | Core columns |
|---|---|
| Submission | submitting_lab, submit_date, receiver |
| Patient | patient_id, patient_name, patient_age, patient_gender, patient_phone |
| Isolation | isolation_date, province, city, district, facility |
| Sample | sample_source, sample_type, food_category, food_name, collection_date |
| Clinical | symptoms, onset_date, diagnosis, outcome, hospital |
| Outbreak association | outbreak_id, cluster_note |

**extra JSON** stores custom fields (unconstrained by the table schema); UPSERT automatically merges existing extra.

```python
from hermes_bacmap.services.strain_metadata import StrainMetadataService

svc = StrainMetadataService("data/hermes_bacmap.sqlite")

# 写入（首次 INSERT，再次 UPDATE）
svc.upsert("SAM-TYP-001", {
    "patient_name": "张三",           # → 核心列
    "patient_age": 35,                # → 核心列
    "province": "北京",               # → 核心列
    "case_type": "暴发",              # → extra JSON
    "report_status": "已报",          # → extra JSON
})

# 搜索
results = svc.search(province="北京", isolation_date_from="2024-01-01")
results = svc.search(extra={"report_status": "已报"})
```

### lab_results (wet-lab results)

**EAV pattern** (Entity-Attribute-Value), one row per lab result:

| category | test_name | Example |
|---|---|---|
| ast | 氨苄西林 | result=16, unit=ug/mL, interpretation=R |
| ast | 环丙沙星 | result=0.5, unit=ug/mL, interpretation=S |
| serology | O antigen | result=O4, method=antiserum |
| biochemical | oxidase | result=阴性 |
| pcr | invA | result=positive, method=qPCR |

```python
from hermes_bacmap.services.lab_results import LabResultService

svc = LabResultService("data/hermes_bacmap.sqlite")

# 批量导入药敏
svc.add_batch("SAM-TYP-001", "ast", [
    {"test_name": "氨苄西林", "result": "16", "unit": "ug/mL", "interpretation": "R"},
    {"test_name": "环丙沙星", "result": "0.5", "unit": "ug/mL", "interpretation": "S"},
])

# 查询
ast = svc.get_by_strain("SAM-TYP-001", category="ast")
resistant = svc.search(category="ast", interpretation="R")
```

### Profile Template System (extensible)

```yaml
# metadata_profiles/cdc_china.yaml
name: cdc_china
extends: default

fields:
  - {name: case_type, type: enum, options: [散发, 暴发, 输入性], required: true}
  - {name: report_status, type: enum, options: [草稿, 待审, 已报, 退回]}
  - {name: sequencing_platform, type: enum, options: [MiSeq, NextSeq, NovaSeq, GridION]}
```

User customization only requires creating a YAML file — no code or schema changes.

### Cross-Table Joins (wet-lab vs bioinformatics)

```sql
SELECT m.strain_id,
       m.patient_name, m.province,
       lr.result AS wet_serotype,
       json_extract(g.payload_json, '$.serotype.sistr') AS in_silco_serotype
FROM strain_metadata m
JOIN lab_results lr ON m.strain_id = lr.strain_id AND lr.category = 'serology'
JOIN genome_objects g ON m.strain_id = g.strain_id
WHERE m.province = '北京';
```

---

## 14. Orchestration Scripts

| Script | Lines | Function |
|---|---|---|
| `run_analysis.py` | 295 | end-to-end orchestrator (--sample / --all / --snp / --status) |
| `ingest_results.py` | 909 | GOM ingestion (--sample / --all / --snp, with deduplication + version management) |
| `generate_report.py` | 866 | HTML reports (--sample / --all / --cohort; `--pdf` produces PDF via headless chromium) |
| `validate_analytical.py` | 382 | analytical validation harness (§12.3: gold standard vs actual output → metrics.json + report) |
| `benchmark_batch.py` | 283 | 96-strain benchmark (prepare downsampling / run isolated batches / extrapolate extrapolation report) |
| `download_gold_standard.py` | 211 | ENA FASTQ download (aria2c multi-threaded + MD5 verification) |
| `generate_snp_matrix.py` | 179 | VCF → FASTA SNP matrix (whole-genome mode) |
| `collect_summary.py` | 120 | Snakemake script: aggregates all step results into summary.json |
| `generate_snp_summary.py` | 107 | treefile + FASTA → snp_summary.json |
| `call_pathotype.py` | 75 | DEC pathotype calling (stx1/stx2/eae/ipaH/est/elt/aggR) |
| `assemble_gold_standard.sh` | 60 | batch Shovill assembly |
| `species_validation_invA.sh` | 67 | invA species validation (bwa mem + samtools) |
| `assembly_validation_blastn.sh` | 80 | contig blastn species validation |

### run_analysis.py key features

- **Sample validation**: an unknown sample_id raises an error and lists valid samples
- **Timeout protection**: subprocess.run timeout=7200s prevents indefinite hangs
- **Environment preservation**: `{**os.environ, PATH=...}` retains HOME/TMPDIR etc.
- **Failure diagnostics**: prints 3-step diagnostic advice (check logs → unlock → retry)
- **Partial-completion detection**: in --all mode, samples missing a summary are counted and exit 1 is returned
- **SNP support**: --snp triggers the cohort-level SNP pipeline

---

## 15. CI/CD and Quality Assurance

### CI Pipeline (6 jobs)

| Job | Content | Trigger |
|---|---|---|
| `lint` | ruff check + ruff format --check | PR + push to main |
| `typecheck` | mypy --strict src/hermes_bacmap/ | PR + push to main |
| `unit-tests` | pytest --cov + Codecov upload | PR + push to main |
| `pre-commit` | .pre-commit-config.yaml hooks | PR + push to main |
| `security-scan` | pip-audit --strict (CVE checks) | PR + push to main |
| `changelog-check` | forces CHANGELOG.md updates | PR to main |

### Test Coverage

| Test file | Tests | Coverage |
|---|---|---|
| `test_genome_object_service.py` | 50 | GOM schema/CRUD/versioning/files/events/factory functions |
| `test_deterministic_verifier.py` | 21 | Verifier's four rule categories (positive/negative/boundary) |
| `test_cohort_ingest.py` | 9 | cohort creation/deduplication/events/linking/versioning/files/queries/tree/distances |
| `test_env.py` | 5 | environment validation (Python/pixi/toolchain) |
| **Total** | **96** | |

### Pre-commit Hooks

ruff + mypy --strict + markdownlint + trailing-whitespace + detect-secrets

---

## 16. Reference Databases

### Species Identification Databases

| File | Size | Content |
|---|---|---|
| `species/markers.fasta` | 8.3 KB | merged 5-gene database (invA + uidA + ipaH + toxR + tlh) |
| `salmonella_invA.fasta` | 2.3 KB | standalone invA database (M90846.1, 2176bp) |
| `uidA_ecoli.fasta` | 1.3 KB | uidA (NC_000913.3, 1190bp) |
| `ipaH_shigella.fasta` | 1.9 KB | ipaH (NC_004337.2, 1827bp) |
| `toxR_vpara.fasta` | 1.3 KB | toxR (BA000031.2) |
| `tlh_vpara.fasta` | 1.7 KB | tlh (M36437.1) |

### AMR / Virulence / Plasmid Databases

| File | Size | Source |
|---|---|---|
| `amr/card.fasta` | 6.5 MB | CARD (Comprehensive Antibiotic Resistance Database) |
| `amr/vfdb.fasta` | 6.3 MB | VFDB (Virulence Factor Database) |
| `plasmid/plasmidfinder.fasta` | 437 KB | PlasmidFinder (CGE) |

### Serotype Databases

| File | Size | Content |
|---|---|---|
| `serotype/ecoh.fasta` | 782 KB | E. coli O/H antigens (597 seqs) |
| `serotype/shigella.fasta` | 122 KB | Shigella antigens (95 seqs, ported from ShigATyper) |

### SNP Reference Genome

| File | Size | Content |
|---|---|---|
| `genomes/salmonella_LT2.fasta` | 4.7 MB | NC_003197.2 (S. enterica LT2 chromosome, 4,857,450bp) |

### V. parahaemolyticus Virulence Databases

| File | Size | Content |
|---|---|---|
| `virulence/tdh.fasta` | 1.2 KB | tdh (D90238.1, thermostable direct hemolysin) |
| `virulence/trh.fasta` | 1.7 KB | trh (AY586619.1, TDH-related hemolysin) |
| `virulence/vpara_targets.fasta` | 5.7 KB | merged toxR + tlh database |

---

## 17. Multi-Method Species Identification System

Five methods coexist (uniformly switched via `species_mode`); identification results are written to the GOM and follow the strain, and `bio_species_compare` produces a cross-method arbitration matrix.

| Method | species_mode | Database (size) | Per-strain runtime | Status |
|---|---|---|---|---|
| marker target genes | `simple` | 0 (already present) | seconds | ✅ 17/17 verified |
| skani curated panel | `panel` | 1-2 GB | seconds | ✅ 17/17 verified |
| skani full GTDB database | `skani_gtdb` | 30 GB | seconds | code ready |
| Mash RefSeq | `mash_refseq` | 159 MB | seconds | ✅ 17/17 verified |
| sourmash gather | `sourmash` | 3.7 GB | seconds | code ready |
| GTDB-Tk + CheckM2 | `standard` | 98 GB + 3 GB | minutes | code ready |

Kraken2 reads-level pre-screening is an independent switch (`kraken2_prefilter`) and can be combined with any mode.

### Arbitration Rules

Priority `gtdbtk > {skani_gtdb, panel, sourmash, mash_refseq} > marker`; same-tier conflict → NEEDS_REVIEW; Shigella/EIEC ↔ E. coli exemption (expected_divergence).

### Deployment

- **CLI**: `pixi run setup` (interactive tier selection)
- **Conversational**: `bio_db_setup` tool (AI executes automatically, background deployment + `bio_db_status` follow-up)
- Missing databases auto-degrade to marker with a WARNING (pipeline not interrupted)

### marker near-neighbor guard

A tlh single-gene hit with identity <90% → the species call is suppressed to Unknown (prevents cross-reaction with the *V. alginolyticus* tlh homolog; see [cross-reaction case](cases/species-crossreaction.md)).

## 18. Gold Standard Validation Dataset

### 12 Strains

| Sample ID | Species | Serotype | MLST | Source | Purpose |
|---|---|---|---|---|---|
| SAM-TYP-001 | S. enterica | Typhimurium | ST19 | ENA | reference strain |
| SAM-TYP-002 | S. enterica | Typhimurium | ST19 | ENA | duplicate (SNP validation) |
| SAM-ENT-003 | S. enterica | Newport | ST45 | ENA | serotype diversity |
| SAM-ENT-004 | S. enterica | Thompson | ST26 | ENA | serotype diversity |
| SAM-INF-005 | S. enterica | Infantis | ST32 | ENA | emerging MDR clone |
| SAM-NEW-006 | S. enterica | Newport | ST118 | ENA | Newport diversity |
| SAM-CTX-008 | S. enterica | Typhi | — | ENA | CTX-M-15 + phylogenetic outgroup |
| SAM-DEC-012 | E. coli | O153:H2 | — | ENA | DEC negative control |
| SAM-SHI-013 | Shigella | S. flexneri 2a | — | ENA | ipaH validation |
| SAM-EIEC-014 | E. coli (EIEC) | O152:H28 | — | ENA | ipaH + ecoh dual validation |
| SAM-ECO-011 | E. coli | K-12 MG1655 | — | DDBJ/ENA | species negative control (uidA+/invA−) |
| SAM-MCR-010 | S. enterica | Typhimurium | — | ENA | mcr-1 AMR validation (V0.7 re-run) |

### Validation Matrix

| Verification item | Result |
|---|---|
| Species identification (invA/uidA/ipaH) | 10/10 ✅ |
| Salmonella serotype (SISTR) | 7/7 ✅ |
| DEC serotype (ecoh_serotyper) | 3/3 ✅ |
| Shigella serotype (shigella_serotyper) | 1/1 ✅ |
| SNP phylogenetic tree topology | ✅ (Newport clustering + longest Typhi branch) |
| SNP distance matrix | ✅ (TYP-001 vs TYP-002 = 1,666 SNPs, lowest) |

---

## Appendix: Environment and Dependencies

### Python Dependencies (uv + pyproject.toml)

```
biopython >= 1.83     # 序列操作
pydantic >= 2.0       # 数据模型
pytest >= 8.0         # 测试
ruff >= 0.5           # lint + format
mypy >= 1.10          # 类型检查
```

### Bioinformatics Tools (pixi + pixi.toml)

```
fastp >= 1.3.5        # QC
shovill >= 1.1.0      # 组装
blast >= 2.16         # BLAST
bwa >= 0.7.17         # 比对
samtools >= 1.20      # BAM 操作
bcftools >= 1.20      # 变异检测
seqkit >= 2.8         # 序列统计
sistr_cmd >= 1.1.3    # Salmonella 血清型
abricate >= 1.4.0     # AMR/毒力/质粒
iqtree >= 3.1.2       # 系统发育树
snakemake 7.32.*      # 工作流引擎
```

### Standalone Environment

```
pixi (gmlst now included)/          # Python 3.12 (gmlst 需要 ≥3.12)
```

---

## 14. Agent Autonomous Data-Mining Layer (DuckDB + MMseqs2 Discovery Engine)

Answers "how can the LLM autonomously discover meaningful genes from existing data":
cross-genome pattern recognition needs two layers of capability — a compute layer
(clustering) + a query layer (federated analytics). The design follows the
**zero-index principle**: no new data is written to the GOM; DuckDB directly scans
existing result files (columnar + vectorized + predicate pushdown), so storage
overhead is zero.

### Three-Tool Collaboration Model

| Tool | Role | Underlying |
|---|---|---|
| `bio_pangenome` | compute layer: CDS protein clustering → cluster×sample matrix | mmseqs2 easy-linclust (linear time) |
| `bio_analytics_query` | query layer: read-only SQL federated queries | DuckDB in-memory connection + view registration |
| `bio_differential_genes` | statistics layer: two-group differential enrichment analysis | Fisher's exact test (pure Python) + BH correction |

### Data Flow

```
annotation.json (protein_seq, already present)
    → extract_proteins → all_proteins.faa ({sample}__{locus_tag} IDs carry genome attribution)
    → mmseqs2 easy-linclust → cluster.tsv (rep → members)
    → build_matrix → presence_matrix.parquet (cluster_id/named_gene/is_novel/n_genomes/per-sample 0-1)
    → DuckDB view pangenome (federated queries with gapit_card/gapit_vfdb/samples in the same database)
```

### Typical Discovery Workflow (outbreak investigation)

```
User: "Comparing these 12 outbreak strains against the background, which genes are distinctive?"

1. AI → bio_differential_genes(group_a=outbreak strains, group_b=background strains, source=gapit_vfdb)
   ← known-gene enrichment (e.g. tdh 12/12 vs 5/284, q<1e-10)
2. AI → bio_pangenome(samples=all) + bio_analytics_query(
     sql: SELECT cluster_id, n_genomes FROM pangenome
          WHERE is_novel AND "SAM-outbreak-01"=1 ... GROUP BY ...)
   ← novel gene clusters (no named annotation yet but recurring across genomes)
3. AI interpretation → candidate new markers → validation (panel screening) → registration (gapit db build)
```

### DuckDB View Registration (connect())

| View | Source file | Key columns |
|---|---|---|
| `gapit_card` / `gapit_vfdb` / `gapit_plasmidfinder` | `*/amr/*.tsv` etc. (abricate format) | strain_id, gene, identity, coverage, database, product |
| `samples` | annotation directories ∪ gapit strains | strain_id |
| `pangenome` | `pangenome/presence_matrix.parquet` | cluster_id, representative, named_gene, is_novel, n_genomes, per-sample 0/1 |

SQL safety: only a single SELECT/WITH statement is allowed (`_is_readonly_sql`
whitelist + keyword blacklist); multi-statements and COPY/CREATE/ATTACH etc. are all
rejected; the connection is purely in-memory with no persistence side effects.

### Fisher's Exact Test Implementation

Exact hypergeometric computation on the 2×2 contingency table (`math.lgamma`, no scipy
dependency); the two-sided p value = the sum of probabilities over the observed point
and all more extreme support points; multiple testing is corrected with
Benjamini-Hochberg FDR (with monotonicity enforcement). Unit tests verify against
hand-computed values (e.g. [[4,0],[0,4]] → p = 2/C(8,4) = 0.0286).

### Related Modules

| Module | Content |
|---|---|
| `engine/backends/mmseqs2.py` | MMseqs2 backend (easy-linclust wrapper + cluster TSV parsing, registered in _BUILTINS) |
| `analysis/pangenome.py` | protein extraction / clustering orchestration / matrix building / Parquet export / PangenomeResult |
| `analysis/analytics.py` | view registration / read-only query / differential_genes / gene_prevalence |
| `tools/discovery.py` | 3 Hermes handlers (@tool_handler, JSON returns) |

---

## 15. External Scientific Data Connectors + Numeric Provenance Guard (OpenScience-Inspired Layer)

Borrows three mechanisms from the OpenScience research agent: scientific-database
connectors, a conclusion audit gate, and traceable discovery runs. The design
principle stays local-first (no API key, keys never leave the machine).

### 15.1 Literature Connector — `bio_lit_search`

Europe PMC REST (covers PubMed/MEDLINE + life-science preprints, no key).
The "verify" step of the discovery loop: after the AI finds new marker candidates it
searches prior literature, returning title/citations (with PMID/DOI)/abstract
(truncated to 500 characters)/journal/year.

### 15.2 Global Surveillance Connector — `bio_ncbi_pathogen`

NCBI Pathogen Detection (7M+ isolates, no key). The endpoint is the Isolates
Browser's own backend `pathogens-srv` (an undocumented contract verified by live
testing, polite rate limit ≤1 req/s, UA identifies hermes-bacmap):

| action | collection | Purpose |
|---|---|---|
| isolates | isolates | filter surveillance isolates by organism/geo/serovar/year/AST (AST phenotype, AMR genotype, SNP cluster erd_group) |
| amr | amr | MicroBIGG-E AMR/virulence element lookup (element_symbol, checks whether a candidate marker is already indexed by NCBI) |

Local outbreak strains vs global surveillance comparison: `fq` SOLR filters + `fl`
field list + `start/limit` pagination; response root `ngout.data.content/totalCount`.

### 15.3 Meta-Skill — outbreak-investigation

Orchestrates the discovery loop (borrowing the OpenScience ai4s-agent meta-skill
pattern): group confirmation → `bio_differential_genes` (known-gene enrichment) →
`bio_pangenome` + novel-cluster queries → `bio_lit_search` (literature verification) →
report (citations with PMID). Each stage's artifacts are written to disk + recorded
in GOM. See skills/outbreak-investigation/.

### 15.4 Discovery-Run GOM Ingestion (Traceable Discovery)

- `run_pangenome` persists `pangenome/summary.json`
- the differential handler persists `analytics/differential_{source}.json`
- `ingest_results.py --discovery` registers cohort objects:
  - `cohort:pangenome` (registers the matrix Parquet file artifact + `pangenome_clustered` event)
  - `cohort:discovery-{source}` (`differential_computed` event)
  - idempotent: unchanged content is skipped; changes → new version (following the cohort SNP pattern)

### 15.5 Numeric Provenance Guard — verify_numeric_provenance

`analysis/provenance.py` (borrowing the OpenScience.ai orphan-claim guard):
every number in an AI report (ratios, percentages, p/q values, counts) must trace
back to the set of numbers output by the GOM/tools; deterministic regex extraction,
no LLM.

- Tolerance: 3-decimal rounding + percentage↔fraction conversion (33.3% ↔ 0.333)
- Exemptions: isolated single digits (structural text like "stage 3", "v2")
- Both parts of a ratio `12/12` are checked; scientific notation `1e-10` and thousands separators `384,211` are supported
- `collect_numbers(payload)` recursively flattens the GOM payload into an evidence set
- Hooked into the interpret-results skill: self-check before report delivery; orphans must be fixed

### 15.6 New Module Inventory

| Module | Content |
|---|---|
| `services/literature.py` | Europe PMC search (urllib, 30s timeout, error-safe) |
| `services/ncbi_pathogen.py` | pathogens-srv connector (isolates + amr dual collections) |
| `tools/connectors.py` | bio_lit_search / bio_ncbi_pathogen handlers |
| `analysis/provenance.py` | numeric-claim extraction + evidence-set collection + orphan determination |
| `skills/outbreak-investigation/` | meta-skill (SKILL.md + worked-example reference) |

---

## 16. L2 Sandbox + Capability-Evolution Registry Layer (P2/P3)

### 16.1 L2 Controlled Exploration (project.md §L2 three tools)

| Tool | Capability | Implementation highlights |
|---|---|---|
| `bio_sandbox_exec` | AI-written Python executed in a subprocess | cwd=results/sandbox/<session>/, variables persisted per session via pickle, timeout protection (-u unbuffered partial output recoverable), executed code saved as run_NNNN.py for audit; **outputs entering reports require user sign-off** |
| `bio_sql_query` | read-only GOM SQLite queries | opened via ro URI + read-only guard (reuses _is_readonly_sql); empty sql lists core tables; payload_json can be mined with json_extract |
| `bio_plot` | quick plots | matplotlib Agg, bar/line/scatter/hist/heatmap → results/plots/*.png (filename sanitization); custom plots go through the sandbox |

Sandbox code can access the results directory via `$BACMAP_RESULTS`; sessions are isolated (the session name isolates the variable space).

### 16.2 Capability-Evolution Registration (discover→verify→register→deploy closed loop)

| Tool | Capability | Implementation highlights |
|---|---|---|
| `bio_db_build` | custom gapit screening databases | wraps `gapit db build` (abricate ~~~ / gapit\| header format, nucl/prot auto-detection), injects the pixi PATH into the subprocess (makeblastdb dependency); a built database is immediately usable by gapit screen / bio_gene_scan |
| `bio_marker_register` | new markers into the rule registry | atomic append to marker_rules.yaml (tmp+rename), .bak backup, idempotent re-registration, species-name normalization (spaces→underscores, genus capitalized); optionally appends sequences to markers_v2.fasta (deduplicated by gene name) |

Full evolution flow: discovery via `bio_differential_genes`/`bio_pangenome` → panel
validation → novelty search via `bio_lit_search` → indexing check via
`bio_ncbi_pathogen` (MicroBIGG-E) → rules entry via `bio_marker_register` →
screening-database build via `bio_db_build` → subsequent pipelines pick it up
automatically.

### 16.3 gapit MCP Integration (documented configuration)

The Hermes plugin API (register_tool/register_skill/register_approval_transport) has
no MCP registration hook; MCP servers are configured via the Hermes config.yaml.
How to connect gapit's built-in MCP server (`gapit mcp`):

```yaml
# ~/.hermes/config.yaml （或项目 config）
mcp_servers:
  gapit:
    command: /path/to/.pixi/envs/default/bin/gapit
    args: [mcp]
```

Once connected, the LLM can directly invoke the full gapit feature set (screen/db search/db build/summary).

### 16.4 New Modules

| Module | Content |
|---|---|
| `analysis/sandbox.py` | L2 executor (subprocess + runner + session-variable pickle) |
| `analysis/plotting.py` | quick rendering of five chart types |
| `services/gapit_ops.py` | gapit db build wrapper (PATH injection + record-count parsing) |
| `services/marker_registry.py` | atomic rule-file registration (backup/idempotency/normalization) |
| `tools/sandbox.py` / `tools/curation.py` | 5 handlers (39 tools) |
