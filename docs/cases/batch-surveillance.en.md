# Batch Surveillance: 10 Mixed Isolates

## Scenario

A routine surveillance batch containing 10 mixed-species isolates (e.g., Salmonella, DEC, Shigella/EIEC, V. parahaemolyticus).
Hermes automatically routes each sample to the matching analysis pipeline based on species marker genes.

## Standard Operating Procedure

### 1. Batch analysis

```bash
python scripts/run_analysis.py --all
```

- Reads `workflows/bacmap/config/samples.tsv` automatically
- Each sample runs: QC → assembly → species identification → serotyping / MLST / AMR / virulence
- Builds the cohort-level SNP tree (Salmonella)

### 2. Ingest results

```bash
python scripts/ingest_results.py --all
```

- Writes results into the GOM (Genome Object Model)
- Automatic deduplication, versioning, and file artifact registration

### 3. Generate reports

```bash
python scripts/generate_report.py --all
```

- Generates a standalone HTML report per isolate
- Summarizes into a batch summary

## Status Monitoring

```bash
python scripts/run_analysis.py --status
```

Shows which stage each sample is currently in (qc / assembly / species / typing / amr / report).

## Hermes Natural-Language Query Examples

After starting `hermes chat`:

```
> 列出所有样本
> 哪些样本是 Typhimurium?
> 搜索 blaCTX
> SAM-DEC-012 的致病型是什么？
> 比较 SAM-SHI-013 和 SAM-EIEC-014
```

## Expected Results

- Automatic species routing: invA → Salmonella, uidA → DEC, ipaH → Shigella/EIEC, toxR/tlh → V. parahaemolyticus
- No manual species specification needed
- Mixed batches complete end-to-end analysis in a single command
