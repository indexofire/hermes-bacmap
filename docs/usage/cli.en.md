# Command-Line Tools

Hermes-bacmap provides four orchestration scripts covering the full workflow:
**run analysis → ingest results → generate reports → switch LLM**.
All scripts live in `scripts/` and must be run from the project root.

```bash
# 所有命令均在项目根目录执行
cd ~/repo/github/hermes-bacmap
```

## run_analysis.py — End-to-End Analysis Orchestrator

Triggers the Snakemake DAG and automatically performs QC → assembly → species identification → MLST → serotyping →
AMR → annotation → summarization. Species routing is fully automatic: invA-positive goes down the Salmonella
pipeline, uidA-positive goes down the DEC pipeline, and so on.

```text
usage: run_analysis.py [-h] (--sample SAMPLE | --all | --snp | --status) [--cores CORES]

options:
  --sample SAMPLE  分析单个样本（如 SAM-TYP-001）
  --all            批量分析 samples.tsv 中所有样本
  --snp            运行 cohort 级 SNP 系统发育分析
  --status         查看所有样本分析进度
  --cores CORES    Snakemake 并行核数（默认 8）
```

### Single-Sample Analysis

```bash
python scripts/run_analysis.py --sample SAM-TYP-001
```

Output layout:

```
results/SAM-TYP-001/
├── qc/SAM-TYP-001_fastp.json          质控报告
├── assembly/contigs.fasta              组装结果
├── assembly/assembly_stats.tsv         组装统计
├── species/species_id.json             物种鉴定
├── typing/mlst.tsv                     MLST
├── typing/sistr.json                   血清型（Salmonella）
├── amr/abricate_{card,vfdb,plasmidfinder}.tsv   AMR / 毒力 / 质粒
├── annotation/annotation.json          基因组注释
└── report/SAM-TYP-001_summary.json     汇总
```

### Batch Analysis

```bash
# 分析 samples.tsv 中全部样本（10 株 Gold Standard）
python scripts/run_analysis.py --all

# 限制 4 核（低配机器）
python scripts/run_analysis.py --all --cores 4
```

`--all` detects completed samples and skips them; samples missing a summary are tallied at the end and flagged with exit code 1.

### Checking Status

```bash
python scripts/run_analysis.py --status
```

Example output:

```
分析状态：
  SAM-TYP-001    completed   Salmonella Typhimurium ST19
  SAM-DEC-012    completed   E. coli O153:H2
  SAM-SHI-013    in-progress (assembly done)
  SAM-EIEC-014   not-started

完成 8/10 · SNP cohort: ready
```

### SNP Cohort Analysis

```bash
# 需 ≥2 株同物种样本已完成单株分析
python scripts/run_analysis.py --snp
```

Triggers the 5-step SNP pipeline: per-isolate BWA alignment → joint variant calling → whole-genome SNP matrix → IQ-TREE tree building → distance matrix summary. See the [Snakemake pipeline](../architecture/pipeline.md).

### Key Features

- **Sample validation**: an unknown sample_id raises an error and lists the valid samples
- **Timeout protection**: subprocesses time out after 7200 s to prevent infinite hangs
- **Failure diagnostics**: on failure, prints a 3-step diagnostic suggestion (check logs → unlock → retry)

## ingest_results.py — GOM Ingestion

Writes Snakemake results into the Genome Object Model (SQLite). Automatic versioning, deduplication, and SHA256 verification.

```text
usage: ingest_results.py [-h] (--sample SAMPLE | --all | --snp)
```

```bash
# 单株入库
python scripts/ingest_results.py --sample SAM-TYP-001

# 全量入库（先于 SNP）
python scripts/ingest_results.py --all

# SNP cohort 入库（在 --all 之后执行）
python scripts/ingest_results.py --snp
```

Ingestion logic:

| strain_id state | Same pipeline_version | Behavior |
|---|---|---|
| Does not exist | — | Creates v1 |
| Already exists | Yes | Skips (`⏭️ 已存在 v1, skipped`) |
| Already exists | No | Creates a new version v+1 (Immutable + Version First) |

Each ingested isolate creates: 1 ANALYSIS object + 9 file artifacts + 5 lifecycle events. See the [GOM data model](../architecture/gom.md).

## generate_report.py — HTML Reports

Generates visual HTML reports integrating species, MLST, serotype, AMR, annotation, and the SNP distance matrix.

```text
usage: generate_report.py [-h] (--sample SAMPLE | --all | --cohort)
```

```bash
# 单株报告
python scripts/generate_report.py --sample SAM-TYP-001
# → results/SAM-TYP-001/report/SAM-TYP-001_report.html

# 全量报告
python scripts/generate_report.py --all

# Cohort SNP 报告（系统发育树 + 距离矩阵）
python scripts/generate_report.py --cohort
# → results/snp/cohort_report.html
```

## switch_llm.py — LLM Provider Switching

Switches the Hermes Agent inference backend (cloud / local). See [Local LLM Configuration](../installation/local-llm.md).

```text
usage: switch_llm.py [-h] {zai,ollama,vllm,llamacpp,status}
```

```bash
# 查看当前 provider
python scripts/switch_llm.py status

# 切到 Ollama（需先 ollama serve &）
python scripts/switch_llm.py ollama

# 切回云端 Z.AI（GLM-5.2）
python scripts/switch_llm.py zai

# 切换后重启 Hermes
hermes chat
```

## Helper Scripts

| Script | Purpose |
|---|---|
| `download_gold_standard.py` | Downloads the 10-isolate validation dataset from ENA (aria2c + MD5 verification) |
| `generate_snp_matrix.py` | VCF → FASTA SNP matrix (whole-genome mode) |
| `collect_summary.py` | Snakemake script: aggregates all steps into summary.json |
| `generate_snp_summary.py` | treefile + FASTA → snp_summary.json |
| `call_pathotype.py` | DEC pathotype determination (stx1/stx2/eae/ipaH/...) |

## Typical Workflow

```bash
# 1. 批量分析
python scripts/run_analysis.py --all

# 2. SNP cohort（可选，需同物种 ≥2 株）
python scripts/run_analysis.py --snp

# 3. 入库（先单株后 SNP）
python scripts/ingest_results.py --all
python scripts/ingest_results.py --snp

# 4. 报告
python scripts/generate_report.py --all
python scripts/generate_report.py --cohort
```

!!! tip "Resuming after interruption"
    Snakemake state persists in `.snakemake/`. After a session is interrupted, first check progress with
    `run_analysis.py --status`, then resume with `run_analysis.py --sample SAM-XXX`. If the directory is locked,
    see [Troubleshooting](../reference/troubleshooting.md).

Beyond the command line, you can also interact in natural language via the [Hermes Agent](hermes-agent.md) or browse results in the [Web UI](web-ui.md).


## Database Deployment

```bash
# 交互式选择鉴定数据库档位
pixi run setup

# 非交互直接安装指定档位
python scripts/setup_databases.py --tier mini --yes

# 预览（不执行）
python scripts/setup_databases.py --tier mini --dry-run
```

## Switching Species Identification Methods

```bash
# 使用 skani ANI 面板鉴定（需先部署 mini 档）
python scripts/run_analysis.py --sample SAM-TYP-001 --species-mode panel

# 使用 GTDB-Tk 标准模式（需 >=140GB RAM + 98GB 数据库）
python scripts/run_analysis.py --sample SAM-TYP-001 --species-mode standard
```

## Verifying Identification Accuracy

```bash
# 下载 NCBI 病原追踪基因组作为验证数据集
python scripts/download_validation_genomes.py

# 运行三方法验证
python scripts/validate_species_id.py --methods marker panel mash_refseq
```

## Ingesting and Backfilling Species Identification Results

```bash
# 常规入库（自动包含物种鉴定结果）
python scripts/ingest_results.py --all

# 存量数据回填物种鉴定
python scripts/ingest_results.py --backfill-species
```
