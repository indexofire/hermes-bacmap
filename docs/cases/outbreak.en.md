# Outbreak Investigation Case Study

This case study demonstrates SNP phylogenetic analysis of **7 Salmonella isolates** to identify potential
outbreak clusters. Applicable scenarios: foodborne disease outbreak trace-back, laboratory cross-contamination
investigation, transmission chain confirmation.

## Scenario

A municipal CDC received 7 *Salmonella enterica* isolates within two weeks, from different patients but with epidemiological information suggesting a possible common exposure source. Requirements:

- Use WGS to confirm the relatedness between isolates
- Identify common-source transmission chains (threshold ≤5 SNPs)
- Produce submittable SNP distance matrix and phylogenetic tree reports

Dataset (ENA Gold Standard):

| Sample | Serotype | MLST | Role |
|---|---|---|---|
| SAM-TYP-001 | Typhimurium | ST19 | Suspected outbreak isolates |
| SAM-TYP-002 | Typhimurium | ST19 | Suspected related to 001 |
| SAM-ENT-003 | Newport | ST45 | Control |
| SAM-ENT-004 | Thompson | ST26 | Control |
| SAM-INF-005 | Infantis | ST32 | Emerging MDR clone |
| SAM-NEW-006 | Newport | ST118 | Newport diversity |
| SAM-CTX-008 | Typhi | — | Outgroup (CTX-M-15) |

## Step 1 · Per-Isolate Analysis First

The SNP pipeline requires every isolate to have completed assembly and species identification:

```bash
# 批量分析全部 7 株
python scripts/run_analysis.py --all

# 检查状态
python scripts/run_analysis.py --status
# 完成应为 7/7
```

Or with the Hermes Agent:

```
> 分析所有样本
```

Confirm every isolate has species_verdict = Salmonella (invA positive). If other species sneak in, the SNP cohort fails due to reference genome mismatch.

## Step 2 · Trigger the SNP Cohort Pipeline

```bash
python scripts/run_analysis.py --snp
```

Or with the Hermes Agent:

```
> 跑 SNP 分析
```

This triggers the 5-step workflow (see [Snakemake pipeline](../architecture/pipeline.md#snp-管线5-步)):

```
✓ snp_calling (×7)        每株 BWA → LT2 参考基因组 → BAM
✓ joint_variant_calling   7 个 BAM 联合 bcftools mpileup → joint VCF
✓ snp_matrix              VCF → FASTA（whole-genome，N 填充缺失）
✓ phylo_tree              IQ-TREE GTR + UFBoot 1000 → Newick
✓ snp_summary             距离矩阵 + 统计 → JSON
```

Key design: **joint calling** (not per-sample calling merged afterwards) guarantees cross-sample genotype
consistency; the **whole-genome matrix** retains all variant sites, with only 4.7% missing filled as N.

## Step 3 · Ingestion and Reports

```bash
# 先入库单株（若尚未）
python scripts/ingest_results.py --all

# 入库 SNP cohort（创建 cohort:salmonella-snp 对象）
python scripts/ingest_results.py --snp

# 生成 cohort 报告
python scripts/generate_report.py --cohort
# → results/snp/cohort_report.html
```

## Step 4 · View the Phylogenetic Tree

```bash
cat results/snp/snp_summary.json | python -m json.tool
```

Or with the Hermes Agent:

```
> 系统发育树
> 比较 SAM-TYP-001 和 SAM-TYP-002
```

Calls `bio_snp_tree`, returning the Newick tree + pairwise distance matrix.

### Expected Statistics

| Metric | Value |
|---|---|
| SNP sites | 122,598 |
| Missing rate | 4.7% |
| Parsimony-informative sites | 55,437 |
| Bootstrap support | All internal branches ≥ 92% |
| Reference genome | NC_003197.2 (LT2, 4.8 Mb, chromosome only) |

### Expected Topology

```
                      ┌── SAM-TYP-001 (Typhimurium)
                 ┌────┤
                 │    └── SAM-TYP-002 (Typhimurium)   ← 最近聚类
                 │
                 │         ┌── SAM-ENT-003 (Newport)
                 │      ┌──┤
                 │      │  └── SAM-NEW-006 (Newport)
   ──────────────┤      │
                 │      └── SAM-INF-005 (Infantis)
                 │
                 ├── SAM-ENT-004 (Thompson)
                 │
                 └── SAM-CTX-008 (Typhi)              ← 最长分支（外群）
```

Key topology correctness checks:

- The two Typhimurium isolates (TYP-001 + TYP-002) cluster together ✅
- The two Newport isolates (ENT-003 + NEW-006) cluster together ✅
- Typhi (CTX-008) has the longest branch (0.677) ✅

## Step 5 · Interpreting the SNP Distance Matrix

The Agent loads the `interpret-results` skill and interprets using the threshold table:

| Sample pair | SNP distance | Interpretation |
|---|---|---|
| **TYP-001 ↔ TYP-002** | **1,666** | Same serotype and ST, but >50 → not recent transmission |
| ENT-003 ↔ NEW-006 | Moderate | Same serotype Newport, different STs (ST45 vs ST118) |
| TYP-001 ↔ CTX-008 | ~58,000 | Different serotypes; Typhi as outgroup |

### Outbreak thresholds (from the interpret-results skill)

| SNP distance | Interpretation | Public health action |
|---|---|---|
| **0–5** | **Common-source transmission chain (highly related)** | Launch an epidemiological investigation |
| 6–15 | Possible epidemiological link | Combine with epidemiological information |
| 16–50 | Same lineage | Continue surveillance |
| >50 | Different lineages | Rule out direct transmission |

### Conclusion for this case

Although TYP-001 and TYP-002 are both Typhimurium ST19, their **SNP distance = 1,666** far exceeds the
5-SNP threshold, so **recent common-source transmission is not supported**. They are merely different
lineage members of the same clonal complex.

If two isolates were <5 SNPs apart, the Agent would clearly warn:

```
⚠️ SAM-XXX 与 SAM-YYY 的 SNP 距离为 3，符合同源传播链阈值。
   建议立即启动流行病学联合调查。
```

## Step 6 · GOM Cohort Object

SNP results are ingested as a cohort-level ANALYSIS object (unlike the per-sample objects for individual isolates):

```python
GenomeObject(
    object_type="analysis",
    strain_id="cohort:salmonella-snp",          # 去重键前缀
    organism="Salmonella enterica",
    payload={
        "analysis_type": "snp_cohort",
        "samples": ["SAM-TYP-001", ..., "SAM-CTX-008"],
        "tree_newick": "(SAM-TYP-001:0.005,...",
        "pairwise_distances": {"SAM-TYP-001|SAM-TYP-002": 1666, ...},
        "n_snp_sites": 122598,
        "missing_rate": 0.0467,
    },
    pipeline_version="snp-pipeline-v0.3",
)
```

Each sample's ANALYSIS object additionally records an `snp_finished` event, establishing bidirectional links. File artifacts:

| file_type | File |
|---|---|
| snp_tree_newick | `core.treefile` |
| snp_alignment | `core_snps.fasta` |
| iqtree_report | `core.iqtree` |
| joint_vcf | `joint.vcf.gz` |
| snp_summary | `snp_summary.json` |

See [GOM data model · Cohort SNP ingestion](../architecture/gom.md#cohort-snp-入库设计).

## Key Caveats

!!! warning "Limits of SNP distance interpretation"
    The thresholds (0–5 / 6–15 / >50) are empirical values and must be combined with epidemiological information:

    - Same serotype + same ST + low SNP distance → strong evidence
    - A reference genome from a different source inflates distances systematically
    - Recombination regions (horizontal gene transfer) inflate distances; filter with Gubbins if necessary
    - Treat low-coverage regions (missing_rate >10%) with caution

!!! info "Reference genome selection"
    This case uses LT2 (NC_003197.2, 4.8 Mb chromosome). When analyzing non-Typhimurium serovars, switch to a
    closer reference to reduce the missing rate. The reference must be **chromosome-only**, excluding plasmids
    (`grep -c "^>" genomes/salmonella_LT2.fasta` should return 1).

## Related

- [Single-isolate case study](single-sample.md) — the prerequisite step for outbreak investigation
- [Snakemake pipeline](../architecture/pipeline.md) — 24 rules and the 5-step SNP workflow
- [Skills system](../architecture/skills.md) — the SNP threshold knowledge base of interpret-results
- [Tool list](../reference/tools.md) — details of the `bio_snp_tree` tool
