# Tool List

Hermes-bacmap registers **29 Tools** in two categories: 8 bioinformatics primitives (low-level algorithm wrappers) and 21 high-level analysis tools (business-level workflows).
Every tool implements its handler in the `src/hermes_bacmap/tools/` package (grouped by seq / cli / pipeline / services), with JSON Schemas defined in `schemas.py` and unified registration in `tools/registry.py`.

## Bioinformatics Primitives (8)

Generic sequence and alignment operations, not tied to any specific pathogen.

| Tool | Function | Input | Output | Underlying tools |
|---|---|---|---|---|
| `bio_seq_stats` | FASTA / FASTQ / GenBank statistics | Sequence file path | N50, GC, length distribution, quality distribution | Biopython |
| `bio_seq_ops` | Sequence operations | Sequence file | Reverse complement, translation, GC-skew, motif, ORF, restriction sites, k-mer | Biopython |
| `bio_fastq_qc` | FASTQ QC + adapter detection | FASTQ file | QC JSON (before/after filtering) | fastp |
| `bio_seq_convert` | Format conversion | Sequence file | 9 formats interconverted (FASTA / FASTQ / GenBank / EMBL, etc.) | Biopython |
| `bio_blast` | Local + remote (NCBI) BLAST | query + db | Hit list (identity / coverage / evalue) | blastn / blastp / blastx |
| `bio_align` | Sequence alignment | reads + reference | sorted BAM (with index) | BWA-MEM / minimap2 / STAR |
| `bio_samtools` | SAM / BAM operations | BAM file | index / sort / flagstat / view / depth / faidx / mpileup / consensus / fixmate | samtools (9 subcommands) |
| `bio_variant` | Variant calling | BAM / VCF | mpileup_call / filter / query / annotate / consensus | bcftools |

Low-level alignment is dispatched uniformly through `SequenceMatcher` / `ReadMapper` in the [Engine layer](../architecture/engine.md), automatically selecting blastn / blastp / minimap2 / bwa backends.

## High-Level Analysis Tools (21)

Pathogen-specific business workflows, wrapped as single calls.

| Tool | Function | Input | Output |
|---|---|---|---|
| `bio_analyze_pathogen` | Triggers the full Snakemake workflow (cross-pathogen auto-routing) | `sample_id` | `{sample}_summary.json` |
| `bio_get_result` | Gets a compact per-isolate result summary | `sample_id` | JSON (species / mlst / serotype / amr) |
| `bio_verify_result` | Runs the Deterministic Verifier | `sample_id` | VerificationResult (passed / checks / needs_review) |
| `bio_generate_report` | Generates an HTML report (single isolate / all / cohort) | `sample_id` or `--cohort` | HTML file |
| `bio_list_samples` | Lists all samples with their analysis status | None | Sample status list |
| `bio_gene_scan` | Multi-database gene scanning | `contigs` + `database` | Gene list (identity / coverage) |
| `bio_snp_tree` | Gets the cohort phylogenetic tree + distance matrix | None | Newick + pairwise distances |
| `bio_search_samples` | Natural-language sample search | `query` | Matching samples (with matched field + relevance score) |
| `bio_annotate` | Genome annotation | `contigs_path` | annotation JSON (CDSs + functions) |
| `bio_validate_taxonomy` | Species identification (dual mode) | `sample_id`, `mode` | completeness / contamination / gtdb_taxonomy |
| `bio_diagnose` | Diagnoses pipeline failures | `log_path` or `stderr_text` | Error type / root cause / affected rules / fix commands |
| `bio_vpa_serotype` | V. parahaemolyticus O/K serotype prediction | `contigs` path | Serotype (e.g., O3:K6) + confidence + coverage / identity |
| `bio_add_metadata` | Enters/updates strain background metadata | `sample_id` + patient/isolation/outbreak fields | Metadata record |
| `bio_query_metadata` | Queries strain background metadata | Filters: province / outbreak_id / source / date range, etc. | Matching records |
| `bio_add_lab_result` | Enters wet-lab results (AST / serology / biochemistry / PCR) | `sample_id` + lab results | Lab record |
| `bio_query_lab_results` | Queries wet-lab results | Filters: sample / category / test_name / result interpretation | Matching records |
| `bio_cgmlst` | cgMLST trace-back query (nearest-neighbor projection + threshold verdict) | `sample_id` | OUTBREAK/RELATED/UNRELATED + distance |
| `bio_review_flags` | Lists/clears manual review flags | `sample_id` (optional) | Pending items / clearing result |
| `bio_species_compare` | Cross-method species identification agreement matrix + arbitration conclusion | `strain_id` | Method list / agreement / NEEDS_REVIEW |
| `bio_db_setup` | Deploys identification databases (list / run in background) | `action`, `tier` | Tier list / background launch log |
| `bio_db_status` | Queries installed databases + deployment progress | None | manifest listing + log tail |

## Databases Supported by bio_gene_scan

`bio_gene_scan` scans dynamically at runtime and supports 9 databases:

```
card, vfdb, ecoh, plasmidfinder, resfinder, ncbi, megares, victors, ecoli_vf
```

It is driven underneath by `gene_scanner.py` (546 lines), delegating to
[engine.SequenceMatcher](../architecture/engine.md). BLAST return codes are checked, and non-zero codes
raise (preventing silent false negatives).

## bio_search_samples Weighting Strategy

Natural-language search uses field weighting; higher scores rank first:

| Matched field | Score | Example |
|---|---|---|
| serotype exact match | 10 | Search "Typhimurium" → sistr=Typhimurium |
| MLST ST match | 10 | Search "ST2" → mlst_st=2 |
| AMR gene name match | 9 | Search "CRP" → amr genes contain CRP |
| MLST raw text | 8 | Any field in the TSV matches |
| plasmid match | 7 | PlasmidFinder gene name |
| strain_id match | 6 | Sample ID |
| organism match | 5 | Species name |
| FTS5 full-text match | 1 | Fallback tier |

Search flow: iterate over ANALYSIS objects (excluding the `cohort:` prefix) → compute per-field match scores → deduplicate (keep the latest of multiple versions) → return the top 50 sorted by score descending.

## bio_diagnose Error Types

`bio_diagnose` parses Snakemake logs, recognizes the following error categories, and suggests fix commands:

| Error category | Trigger signal | Typical fix |
|---|---|---|
| OutOfMemory | `signal 9 (SIGKILL)` | Lower `--cores` or Shovill `--ram` |
| LockConflict | `Directory cannot be locked` | `snakemake --unlock` |
| MissingTool | `command not found` | `pixi install` |
| MissingDatabase | `database 'X' not found` | Rebuild indexes with `makeblastdb` |
| MissingInput | `MissingInputException` | Check samples.tsv; download data |
| DiskFull | `No space left on device` | Clean up the results directory |
| VersionMismatch | Snakemake version error | Pin 7.32.x |

## bio_verify_result Check Categories

The Deterministic Verifier runs four check categories on per-isolate results (covered by 21 TDD tests):

| Check category | Rule | On failure |
|---|---|---|
| Species | `species_verdict` contains "Salmonella" | FAIL |
| MLST | `mlst` field is non-empty with a numeric ST | WARN |
| Serotype | `serotype.sistr` is non-empty | WARN |
| AMR | Critical genes (CTX-M/NDM/KPC/mcr-1) trigger review | NEEDS_REVIEW |

Code interface:

```python
from hermes_bacmap.analysis.deterministic_verifier import DeterministicVerifier

v = DeterministicVerifier()
result = v.verify_all(summary_dict)
# result.passed              → bool
# result.checks              → list[CheckResult]
# result.needs_human_review  → bool
# result.failed_count        → int
```

## Invocation

Tools are triggered via natural language through the Hermes Agent, or handlers can be called directly in Python:

```python
from hermes_bacmap.tools import list_samples, get_result, search_samples

# 列出样本
print(list_samples({}))

# 获取结果
print(get_result({"sample_id": "SAM-TYP-001"}))

# 检索
print(search_samples({"query": "Typhimurium"}))
```

The Web UI's `/api/search` endpoint also calls the `search_samples` handler directly.

## Related

- [Engine layer](../architecture/engine.md) — low-level algorithm wrappers
- [Snakemake pipeline](../architecture/pipeline.md) — the 24 rules triggered by `bio_analyze_pathogen`
- [Reference databases](databases.md) — the 13 FASTA libraries used by `bio_blast` / `bio_gene_scan`
- [Troubleshooting](troubleshooting.md) — details of the errors `bio_diagnose` recognizes
