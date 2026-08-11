---
name: run-pipeline
description: >
  Pathogen WGS end-to-end analysis pipeline (QC→assembly→species ID→MLST→
  serotype→AMR→annotation→SNP→report). Supports Salmonella, DEC (E.coli),
  Shigella/EIEC, V. parahaemolyticus with automatic species routing.
  Load when user mentions analyzing, running pipeline, 沙门菌, 大肠, 志贺,
  弧菌, serotyping, MLST, AMR, annotation, or requests genome analysis.
  Trigger words: 分析, analyze, pipeline, run, assembly, 血清型, 耐药.
version: 0.2.0
platforms: [linux]
metadata:
  hermes:
    tags: [bioinformatics, pathogen, salmonella, ecoli, shigella, vibrio, public-health]
    category: bioinfo
    requires_toolsets: [terminal]
---

# Pathogen WGS End-to-End Analysis

## When to Use

- User wants to analyze bacterial genome sequencing data
- Input: Illumina paired-end FASTQ (PE100/PE150/PE250/PE300)
- Output: species ID + serotype + MLST + AMR + virulence + plasmid + annotation + report
- Supports 4 pathogens with automatic species routing:
  - **Salmonella** → invA → SISTR + gmlst
  - **E. coli / DEC** → uidA → ecoh_serotyper + pathotype
  - **Shigella / EIEC** → ipaH → shigella_serotyper
  - **V. parahaemolyticus** → toxR+tlh → tdh/trh virulence
- For pathogen-specific details, see references/ directory

## Prerequisites

- Snakemake 7.32.x (pixi)
- Tools: fastp, Shovill, BLAST, gmlst, SISTR, abricate, seqkit, prodigal, IQ-TREE
- Databases: species_markers, CARD, VFDB, PlasmidFinder, Prokka sprot/IS/AMR
- Project root: `~/repo/github/hermes-bacmap`

## Procedure

### Step 1: Check Status

```bash
python scripts/run_analysis.py --status
```

Shows: completed / in-progress / not-started + SNP cohort status.

### Step 2: Run Analysis

```bash
# Single sample (species auto-detected)
python scripts/run_analysis.py --sample SAM-TYP-001

# All samples
python scripts/run_analysis.py --all

# SNP cohort analysis (requires >=2 samples of same species)
python scripts/run_analysis.py --snp
```

Snakemake DAG auto-orchestrates all steps. Species routing is automatic.

### Step 3: Post-Analysis

```bash
python scripts/ingest_results.py --all     # GOM ingest
python scripts/ingest_results.py --snp     # SNP cohort ingest
python scripts/generate_report.py --sample SAM-TYP-001  # HTML report
python scripts/generate_report.py --cohort               # SNP tree report
```

### Step 4: Resume After Disconnect

1. Snakemake continues in background (`.snakemake/` state persists)
2. On reconnect: `python scripts/run_analysis.py --status`
3. Force resume: `python scripts/run_analysis.py --sample SAM-TYP-001`
4. If locked: `cd workflows/salmonella && snakemake --unlock`

## Pipeline Architecture

```
                    FASTQ
                      ↓
            ┌──── fastp (QC) ────┐
            ↓                     ↓
      Shovill (assembly)    species_identify
            ↓                     ↓
      annotation              ┌────┴────┐
      (pyrodigal +            ↓         ↓
       Prokka DBs)      Salmonella   Other species
            ↓                ↓         ↓
      seqkit stats       gmlst     ecoh/shigella/
            ↓                ↓     vpara-specific
      abricate (3 DBs)   SISTR        ↓
            ↓                ↓         ↓
      collect_summary ←───────┴─────────┘
            ↓
      summary.json → report.html
```

## Pitfalls

- **Shovill OOM**: reduce threads or `--ram 4G`
- **Snakemake lock**: `snakemake --unlock` in workflow dir
- **Snakemake v8**: lock to v7.32.x
- **gmlst** runs in the pixi default env (Python 3.12.3 confirmed); no separate venv needed
- For more, see `references/troubleshooting.md`

## Verification

1. `results/{sample}/species/species_id.json` — species confirmed
2. `results/{sample}/typing/mlst.tsv` — valid ST
3. `results/{sample}/report/{sample}_summary.json` — valid JSON
4. Assembly N50 > 10kb — check `assembly_stats.tsv`
5. For pipeline parameters, see `references/pipeline-params.md`

## Pathogen-Specific References

- [references/salmonella.md](references/salmonella.md) — SISTR, invA, salmonella_2 MLST, SNP reference
- [references/dec-shigella.md](references/dec-shigella.md) — ecoh_serotyper, shigella_serotyper, ipaH, pathotype
- [references/vpara.md](references/vpara.md) — toxR, tlh, tdh, trh
