# Single-Isolate Case Study

This case study demonstrates the complete workflow from FASTQ to report, analyzing **SAM-TYP-001** (an S. Typhimurium reference strain from the ENA Gold Standard dataset).

## Scenario

A CDC laboratory received a suspected Salmonella isolate; Illumina PE150 sequencing is already complete. Requirements:

- Confirm the species (is it Salmonella?)
- Determine the serotype and MLST type
- Detect antimicrobial resistance genes and virulence factors
- Generate an archivable HTML report

Expected runtime: about 40–60 minutes (on the recommended hardware tier of 8 cores / 32 GB RAM).

## Step 1 · Check Status

First confirm the sample is in the sample sheet and has not been analyzed yet:

```bash
python scripts/run_analysis.py --status
```

Output:

```
分析状态：
  SAM-TYP-001    not-started
  SAM-TYP-002    not-started
  ...
完成 0/10 · SNP cohort: not-ready
```

Or via the Hermes Agent:

```
> 列出所有样本
```

## Step 2 · End-to-End Analysis

```bash
python scripts/run_analysis.py --sample SAM-TYP-001
```

Or with the Hermes Agent:

```
> 分析 SAM-TYP-001
```

The Agent calls `bio_analyze_pathogen`, triggering the Snakemake DAG. Progress for each step streams live:

```
启动分析 SAM-TYP-001 ...
✓ QC (fastp)                     1-2 min
✓ Assembly (Shovill, N50=215kb)  30-50 min
✓ Species identify               <1 min
✓ MLST (gmlst salmonella_2)      1-2 min
✓ Serotype (SISTR)               <1 min
✓ AMR (abricate ×3)              2-3 min
✓ Annotation (pyrodigal+blastp)  2-3 min
报告汇总已生成
```

Species routing is fully automatic: the `species_identify` rule uses a single BLAST run to detect the five
genes invA / uidA / ipaH / toxR / tlh; an invA hit takes the Salmonella branch (typing_mlst + typing_sistr),
and the remaining rules are pruned from the DAG.

## Step 3 · View Results

```bash
# 紧凑结果摘要（JSON）
cat results/SAM-TYP-001/report/SAM-TYP-001_summary.json | python -m json.tool
```

Or with the Hermes Agent:

```
> SAM-TYP-001 的结果
```

Calls `bio_get_result`, returning the core fields:

```json
{
  "strain_id": "SAM-TYP-001",
  "species_verdict": "Salmonella",
  "serotype": {
    "sistr": "Typhimurium",
    "serogroup": "B",
    "o_antigen": "1,4,[5],12",
    "h1": "i",
    "h2": "1,2"
  },
  "mlst": "SAM-TYP-001\tsalmonella_2\tST19\taroC\tdnaN\themD\t...19",
  "amr": {
    "abricate_card": [
      {"GENE": "blaTEM-1", "%IDENTITY": 99.8, "%COVERAGE": 100.0}
    ],
    "abricate_vfdb": [
      {"GENE": "spiA", "%IDENTITY": 98.5}
    ]
  }
}
```

## Step 4 · Expected Results

| Analysis item | Expected result | Notes |
|---|---|---|
| **Species** | Salmonella (invA positive) | M90846.1 reference hit, identity ≥90%, coverage ≥80% |
| **Serotype** | **Typhimurium** (serogroup B) | SISTR output, O:1,4,[5],12 / H:i / H:1,2 |
| **MLST** | **ST19** (salmonella_2 scheme) | Seven-locus profile: aroC/dnaN/hemD/hisD/pureG/sepA/stra |
| **AMR** | blaTEM-1 (penicillinase) | Detected by abricate against the CARD database |
| **Virulence** | spiA and other Salmonella-specific virulence factors | Detected by abricate against the VFDB database |
| **Assembly N50** | ~215 kb | Meets the "Good" threshold of >100 kb |
| **Annotation rate** | ~72% | pyrodigal CDS + Prokka DB blastp |

## Step 5 · Ingest into GOM

Writes the results into SQLite, establishing traceable, versioned records:

```bash
python scripts/ingest_results.py --sample SAM-TYP-001
```

Ingestion creates:

- 1 `ANALYSIS` GenomeObject (v1, payload contains all results)
- 9 `file_artifacts` (assembly / qc_json / species_blastn / mlst / sistr / amr_card / amr_vfdb / plasmidfinder / summary)
- 5 `events` (uploaded → qc_finished → assembly_finished → amr_finished → report_generated)
- A three-part evidence chain: `pipeline_version=salmonella-workflow-v0.1` + database_versions + tool_versions

Re-running is skipped (`⏭️ 已存在 v1, skipped`). If the pipeline is upgraded and re-run, v2 is created (Immutable + Version First).

## Step 6 · Generate the Report

```bash
python scripts/generate_report.py --sample SAM-TYP-001
# → results/SAM-TYP-001/report/SAM-TYP-001_report.html
```

Or with the Hermes Agent:

```
> 生成 SAM-TYP-001 的报告
```

The report includes: QC statistics charts, assembly metrics, species identification evidence, MLST allele
profile, serotype details, AMR/virulence gene tables, annotation summary, and the three-part evidence chain
(pipeline + DB + tool versions).

## Step 7 · AI Interpretation

Have the Hermes Agent interpret the results by loading the `interpret-results` skill:

```
> SAM-TYP-001 是什么血清型？严重吗？
```

The Agent's interpretation (based on the skill knowledge base):

```
SAM-TYP-001 为 Salmonella Typhimurium（serogroup B），MLST ST19。
Typhimurium 是全球最常见的非伤寒沙门菌血清型之一，与食源性疾病
暴发高度相关。ST19 是其经典序列型。

检出 blaTEM-1（青霉素酶），对青霉素类耐药，但非碳青霉烯酶，
临床严重性为低-中。未检出 CTX-M/NDM/KPC/mcr-1 等关键耐药基因。
```

The Deterministic Verifier automatically checks: species ✅, MLST ✅, serotype ✅, no critical AMR genes ✅ → all PASS.

## Troubleshooting

If the analysis fails:

```bash
# 1. 查看 Snakemake 日志
ls workflows/bacmap/.snakemake/logs/
cat workflows/bacmap/.snakemake/logs/*.snakemake.log | tail -50

# 2. 诊断（Hermes Agent）
> 上次分析失败了，帮我看看
# → 调用 bio_diagnose，解析日志，返回错误类型与修复命令

# 3. 常见问题
#    · 目录被锁：cd workflows/bacmap && snakemake --unlock
#    · Shovill OOM：python scripts/run_analysis.py --sample SAM-TYP-001 --cores 4
#    · 缺失数据库：见参考数据库页

更多见故障排查页。
```

For complete error handling, see [Troubleshooting](../reference/troubleshooting.md).

## Related Case Studies

- [Outbreak investigation case study](outbreak.md) — SNP clustering analysis of 7 Salmonella isolates
- [CLI tools](../usage/cli.md) — full parameters of each script
- [Snakemake pipeline](../architecture/pipeline.md) — the complete DAG of 24 rules
