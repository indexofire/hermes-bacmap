---
name: analyze-salmonella
description: "Salmonella WGS end-to-end analysis (9-step pipeline)"
version: 0.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [bioinformatics, salmonella, public-health, genome-analysis]
    category: bioinfo
    requires_toolsets: [terminal]
    config:
      - key: salmonella.workflow_path
        default: "workflows/salmonella"
---

# Salmonella 全基因组端到端分析

## When to Use

- 用户需要分析 Salmonella（沙门菌）全基因组测序数据
- 输入：Illumina paired-end FASTQ（PE100/PE150/PE250/PE300 均可）
- 输出：物种验证 + 血清型 + MLST + AMR + 毒力 + 质粒 + 汇总报告
- 覆盖 project.md §7.1 核心 9 步 pipeline

## Prerequisites

- Snakemake 7.32.x（`pixi add snakemake`）
- 生信工具：fastp, Shovill, blast, mlst, SISTR, SeqSero2, AMRFinderPlus, abricate, seqkit
- 数据库：invA (M90846.1), AMRFinderPlus DB, vfdb, CARD, plasmidfinder
- Hermes-bacmap 项目根目录在 `~/repo/github/hermes-bacmap`

## Procedure

### Step 1: 检查分析状态

Before starting, check which samples already have results:

```bash
cd ~/repo/github/hermes-bacmap
python scripts/run_analysis.py --status
```

This shows three categories:
- ✅ 完成: samples with `_summary.json` already generated
- 🔄 进行中: samples with partial results (some steps done, some pending)
- ⬜ 未开始: samples with no results yet

### Step 2: 启动自动分析（一次命令，Snakemake DAG 自动编排全流程）

```bash
# Single sample
python scripts/run_analysis.py --sample SAM-TYP-001

# All samples in samples.tsv
python scripts/run_analysis.py --all
```

This runs a single `snakemake --cores 8` command that automatically
executes all 9 steps in correct DAG order per sample:

```
fastp → Shovill → blastn(invA) → MLST → SISTR → SeqSero2 → AMRFinderPlus → abricate(vfdb/card/plasmidfinder) → summary.json
```

**No manual intervention needed between steps.** Snakemake's DAG
handles all dependencies automatically. If interrupted, re-running
the same command resumes from where it stopped (`.snakemake/` state).

### Step 3: 查看自动解读

The script automatically interprets results after Snakemake completes:
- ✅/❌ Species verdict (Salmonella or not)
- 🧬 MLST ST
- 🔬 Serotype (SISTR)
- 💊 AMR genes list

Full JSON report: `results/{sample}/report/{sample}_summary.json`

### Step 4: 断线恢复

If the Hermes session disconnects during analysis:
1. Snakemake continues running in the background (`.snakemake/` state persists)
2. On reconnection, check status: `python scripts/run_analysis.py --status`
3. If in-progress, just wait; Snakemake will complete on its own
4. If you need to force resume: `python scripts/run_analysis.py --sample SAM-TYP-001`
   (Snakemake automatically skips completed steps)

## Pitfalls

- **Shovill OOM**: If assembly fails with memory error, reduce threads or use `--ram 4G`
- **SeqSero2 timeout**: SeqSero2 can hang on poor assemblies; the workflow has a fallback
- **AMRFinderPlus DB missing**: First run needs `amrfinder -u` to download DB
- **Snakemake v8 incompatibility**: Lock v7.32.x (project.md §3.2)
- **conda env creation slow**: First run builds all envs (~10 min); cached afterwards

## Verification

After running, verify:
1. `results/{sample}/species/species_verdict.txt` contains "Salmonella"
2. `results/{sample}/typing/mlst.tsv` has a valid ST (not "N/A")
3. `results/{sample}/report/{sample}_summary.json` exists and is valid JSON
4. Assembly N50 > 10 kb (good quality) — check `assembly_stats.tsv`
