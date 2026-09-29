# Snakemake Pipeline

The workflow engine uses **Snakemake 7.32** (Python DSL), defined in `workflows/bacmap/`. The main entry `Snakefile` orchestrates the per-sample DAG
and the cohort SNP DAG — **24 rules** in total, with fully automatic species routing.

## Species Identification: Two Modes

| Mode | Method | Configuration | External dependencies |
|---|---|---|---|
| `simple` (default) | Target-gene BLAST (invA/uidA/ipaH/toxR/tlh) | `species_mode: simple` | None |
| `standard` (optional) | CheckM2 completeness/contamination + GTDB-Tk taxonomy | `species_mode: standard` | `$CHECKM2DB`, `$GTDBDB` |

The `standard` mode appends CheckM2 and GTDB-Tk results on top of the `simple` results and automatically compares the consistency of the two methods.
It automatically degrades to `simple` when external databases are not configured.

## DAG Overview

```
rule all
  │
  ├── {sample}/report/{sample}_summary.json   (per-sample, ×N)
  │     └── report_summary (collect_summary.py)
  │           ├── qc_fastp → {sample}_fastp.json
  │           ├── assembly_shovill → contigs.fasta
  │           │     └── assembly_stats → assembly_stats.tsv
  │           ├── genome_annotation → annotation.json
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
  └── snp/snp_summary.json   (cohort-level)
        └── snp_summary (generate_snp_summary.py)
              └── phylo_tree → core.treefile + core.iqtree
                    └── snp_matrix → core_snps.fasta
                          └── joint_variant_calling → joint.vcf.gz
                                └── snp_calling (×7) → snps.bam
```

The two DAGs coexist: per-sample rules run independently for each sample; cohort rules fire once after multiple samples are ready.

## Rule List (22 rules)

| # | Rule | Module file | Description |
|---|---|---|---|
| 1 | `all` | `Snakefile` | Main target (per-sample summaries + cohort SNP) |
| 2 | `qc_fastp` | `qc.smk` | fastp QC + adapter trimming |
| 3 | `assembly_shovill` | `assembly.smk` | Shovill assembly (SPAdes + read correction) |
| 4 | `assembly_stats` | `assembly.smk` | seqkit stats summary |
| 5 | `genome_annotation` | `annotation.smk` | pyrodigal CDS + Prokka DB blastp |
| 6 | `species_identify` | `species.smk` | Five-gene species identification (1 BLAST call) |
| 7 | `typing_mlst` | `typing_amr.smk` | gmlst (salmonella_2 scheme) |
| 8 | `typing_sistr` | `typing_amr.smk` | SISTR serotyping + cgMLST |
| 9 | `amr_abricate_vfdb` | `typing_amr.smk` | Virulence gene screening |
| 10 | `amr_abricate_card` | `typing_amr.smk` | AMR gene screening |
| 11 | `amr_abricate_plasmidfinder` | `typing_amr.smk` | Plasmid replicon detection |
| 12 | `dec_ecoh_serotype` | `dec_shigella.smk` | E. coli O:H serotyping |
| 13 | `dec_pathotype` | `dec_shigella.smk` | DEC pathotype determination (STEC/EPEC/EIEC/ETEC/EAEC) |
| 14 | `shigella_serotype` | `dec_shigella.smk` | Shigella serotyping (58 serotypes) |
| 15 | `vpara_targets` | `vpara.smk` | V. parahaemolyticus species identification (toxR + tlh) |
| 16 | `vpara_virulence` | `vpara.smk` | Virulence gene detection (tdh/trh/tlh) |
| 17 | `report_summary` | `report.smk` | collect_summary.py aggregates all steps |
| 18 | `snp_calling` | `snp.smk` | Per-sample BWA mapping to the reference genome |
| 19 | `joint_variant_calling` | `snp.smk` | Multi-sample joint variant calling (bcftools mpileup + call) |
| 20 | `snp_matrix` | `snp.smk` | Whole-genome SNP matrix (FASTA, missing data padded with N) |
| 21 | `phylo_tree` | `snp.smk` | IQ-TREE maximum-likelihood tree (GTR, UFBoot 1000) |
| 22 | `snp_summary` | `snp.smk` | Distance matrix + Newick summary JSON |

## Species Routing (Five-Gene System)

`species_identify` merges 5 species-specific target genes into a single FASTA database (`species/markers.fasta`), completing all species identification with a **single BLAST call**:

| Target gene | Target species | Reference sequence | Length |
|---|---|---|---|
| invA | *Salmonella* spp. | M90846.1 | 2,176 bp |
| uidA | *E. coli* / DEC | NC_000913.3 | 1,190 bp |
| ipaH | *Shigella* / EIEC | NC_004337.2 | 1,827 bp |
| toxR | *V. parahaemolyticus* | BA000031.2 | 643 bp |
| tlh | *V. parahaemolyticus* | M36437.1 | 1,302 bp |

Routing logic:

```
contigs.fasta
    ↓ BLAST vs species/markers.fasta (single call)
    ↓
    invA positive     → Salmonella → typing_mlst + typing_sistr
    uidA positive     → E. coli/DEC → dec_ecoh_serotype + dec_pathotype
    ipaH positive     → Shigella/EIEC → shigella_serotype
    toxR+tlh positive → V. parahaemolyticus → vpara_virulence
```

Subsequent rules (MLST / SISTR / ecoh / shigella / vpara) are activated automatically according to the detected species; unmatched rules are naturally pruned by the Snakemake DAG.

Validation: all 10 gold-standard strains were correctly identified (100% sensitivity, 100% specificity).

## Serotype Branching

Different species go through different serotyping tools; `collect_summary.py` uniformly selects the primary serotype:

```python
if "Shigella" in species and serotype != "Undetermined":
    primary_serotype = shigella_serotype       # shigella_serotyper
elif ecoh_serotype != "-:-":
    primary_serotype = ecoh_serotype           # ecoh_serotyper (DEC/EIEC)
else:
    primary_serotype = sistr_serovar           # SISTR (Salmonella)
```

| Species | Tool | Database | Output |
|---|---|---|---|
| Salmonella | SISTR | salmonella_atdb | serovar + serogroup + O/H antigen |
| DEC / EIEC | ecoh_serotyper | serotype/ecoh.fasta (597 seqs) | O:H serotype |
| Shigella | shigella_serotyper | serotype/shigella.fasta (95 seqs) | species + 58 serotypes |

## SNP Pipeline (5 Steps)

```
Step 1 · snp_calling (per sample)
  raw FASTQ → bwa mem (vs LT2 reference) → samtools sort → BAM

Step 2 · joint_variant_calling (multi-sample joint)
  N BAMs → bcftools mpileup (joint) → bcftools call → joint VCF
  ※ joint calling ensures cross-sample genotype consistency

Step 3 · snp_matrix (whole-genome matrix)
  joint VCF → Python parsing → FASTA alignment
  Strategy: whole-genome mode (all variant sites retained, missing data padded with N)

Step 4 · phylo_tree (phylogenetic tree)
  FASTA → IQ-TREE -m GTR -bb 1000 -alrt 1000
  Output: Newick treefile + IQ-TREE report

Step 5 · snp_summary (distance matrix)
  treefile + FASTA → JSON (Newick + pairwise distances + statistics)
```

### Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Variant calling strategy | **Joint calling** (not per-sample calling then merge) | Avoids cross-sample genotype inconsistency |
| Matrix strategy | **Whole-genome** (not strict core) | Retains all variant sites, missing data padded with N (4.7%), no signal loss |
| Alignment format | **FASTA** (not PHYLIP) | No 10-character name truncation limit |
| Reference genome | NC_003197.2 (LT2, 4.8 Mb) | Chromosome only, plasmids excluded |

### Validation Results (7 Salmonella strains)

| Metric | Value |
|---|---|
| SNP sites | 122,598 |
| Missing rate | 4.7% |
| Parsimony-informative sites | 55,437 |
| Bootstrap support | All internal branches ≥ 92% |
| TYP-001 ↔ TYP-002 distance | 1,666 SNPs (closest, same serotype) |

## Pipeline Parameters

Common Snakemake configuration:

| Parameter | Default | Location |
|---|---|---|
| Threads | 8 | `--cores` |
| Min contig length | 200 | assembly rule |
| invA identity threshold | 90% | species rule |
| invA coverage threshold | 80% | species rule |
| abricate min identity | 80% | amr rules |
| abricate min coverage | 80% | amr rules |
| SNP QUAL filter | 30 | snp_matrix script |
| IQ-TREE model | GTR + UFBoot 1000 | phylo_tree rule |

Assembly quality thresholds (for evaluating whether an assembly is usable):

| Metric | Good | Acceptable | Poor |
|---|---|---|---|
| N50 | >100 kb | 10–100 kb | <10 kb |
| Total contigs | <100 | 100–500 | >500 |
| Total length | 4.5–5.5 Mb | 4–6 Mb | <4 or >6 Mb |
| GC content | 50–53% | 48–55% | <48% or >55% |

Full parameters and per-step runtimes are in `skills/run-pipeline/references/pipeline-params.md`.

## How to Trigger

```bash
# 单株（自动路由）
python scripts/run_analysis.py --sample SAM-TYP-001

# 全量
python scripts/run_analysis.py --all

# SNP cohort（需 ≥2 同物种样本已完成）
python scripts/run_analysis.py --snp

# 状态
python scripts/run_analysis.py --status
```

Snakemake state is persisted in `workflows/bacmap/.snakemake/`, so interrupted runs can resume from checkpoints. If the directory is locked: `cd workflows/bacmap && snakemake --unlock`.

For more troubleshooting, see [Troubleshooting](../reference/troubleshooting.md).
