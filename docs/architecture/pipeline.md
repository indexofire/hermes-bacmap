# Snakemake 管线

工作流引擎采用 **Snakemake 7.32**（Python DSL），定义在 `workflows/salmonella/`。主入口 `Snakefile` 编排 per-sample DAG 与 cohort SNP DAG，共 **22 条规则**，物种路由全自动。

## DAG 概览

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

两条 DAG 并存：per-sample 规则对每个样本独立执行，cohort 规则在多样本就绪后触发一次。

## 规则清单（22 条）

| # | 规则 | 模块文件 | 说明 |
|---|---|---|---|
| 1 | `all` | `Snakefile` | 主目标（per-sample summaries + cohort SNP） |
| 2 | `qc_fastp` | `qc.smk` | fastp 质控 + adapter trimming |
| 3 | `assembly_shovill` | `assembly.smk` | Shovill 组装（SPAdes + read correction） |
| 4 | `assembly_stats` | `assembly.smk` | seqkit stats 统计 |
| 5 | `genome_annotation` | `annotation.smk` | pyrodigal CDS + Prokka DB blastp |
| 6 | `species_identify` | `species.smk` | 五基因物种鉴定（1 次 BLAST） |
| 7 | `typing_mlst` | `typing_amr.smk` | gmlst（salmonella_2 scheme） |
| 8 | `typing_sistr` | `typing_amr.smk` | SISTR 血清型 + cgMLST |
| 9 | `amr_abricate_vfdb` | `typing_amr.smk` | 毒力基因扫描 |
| 10 | `amr_abricate_card` | `typing_amr.smk` | AMR 耐药基因扫描 |
| 11 | `amr_abricate_plasmidfinder` | `typing_amr.smk` | 质粒复制子检测 |
| 12 | `dec_ecoh_serotype` | `dec_shigella.smk` | E. coli O:H 血清型 |
| 13 | `dec_pathotype` | `dec_shigella.smk` | DEC pathotype 判定（STEC/EPEC/EIEC/ETEC/EAEC） |
| 14 | `shigella_serotype` | `dec_shigella.smk` | Shigella 血清型（58 型） |
| 15 | `vpara_targets` | `vpara.smk` | V. parahaemolyticus 物种鉴定（toxR + tlh） |
| 16 | `vpara_virulence` | `vpara.smk` | 毒力基因检测（tdh/trh/tlh） |
| 17 | `report_summary` | `report.smk` | collect_summary.py 聚合所有步骤 |
| 18 | `snp_calling` | `snp.smk` | 每株 BWA 比对到参考基因组 |
| 19 | `joint_variant_calling` | `snp.smk` | 多样本联合变异检测（bcftools mpileup + call） |
| 20 | `snp_matrix` | `snp.smk` | 全基因组 SNP 矩阵（FASTA，N 填充缺失） |
| 21 | `phylo_tree` | `snp.smk` | IQ-TREE 最大似然树（GTR, UFBoot 1000） |
| 22 | `snp_summary` | `snp.smk` | 距离矩阵 + Newick 汇总 JSON |

## 物种路由（五基因系统）

`species_identify` 将 5 个物种特异性靶基因合并为 1 个 FASTA 库（`species_markers.fasta`），**一次 BLAST 调用**完成所有物种鉴定：

| 靶基因 | 目标物种 | 参考序列 | 长度 |
|---|---|---|---|
| invA | *Salmonella* spp. | M90846.1 | 2,176 bp |
| uidA | *E. coli* / DEC | NC_000913.3 | 1,190 bp |
| ipaH | *Shigella* / EIEC | NC_004337.2 | 1,827 bp |
| toxR | *V. parahaemolyticus* | BA000031.2 | 643 bp |
| tlh | *V. parahaemolyticus* | M36437.1 | 1,302 bp |

路由逻辑：

```
contigs.fasta
    ↓ BLAST vs species_markers.fasta（1 次调用）
    ↓
    invA 阳性     → Salmonella → typing_mlst + typing_sistr
    uidA 阳性     → E. coli/DEC → dec_ecoh_serotype + dec_pathotype
    ipaH 阳性     → Shigella/EIEC → shigella_serotype
    toxR+tlh 阳性 → V. parahaemolyticus → vpara_virulence
```

后续规则（MLST / SISTR / ecoh / shigella / vpara）按检出物种自动激活，未匹配的规则被 Snakemake DAG 自然剪枝。

验证：10 株 Gold standard 全部正确鉴定（灵敏度 100%，特异性 100%）。

## 血清型分流

不同物种走不同血清型工具，`collect_summary.py` 统一选择主血清型：

```python
if "Shigella" in species and serotype != "Undetermined":
    primary_serotype = shigella_serotype       # shigella_serotyper
elif ecoh_serotype != "-:-":
    primary_serotype = ecoh_serotype           # ecoh_serotyper (DEC/EIEC)
else:
    primary_serotype = sistr_serovar           # SISTR (Salmonella)
```

| 物种 | 工具 | 数据库 | 输出 |
|---|---|---|---|
| Salmonella | SISTR | salmonella_atdb | serovar + serogroup + O/H antigen |
| DEC / EIEC | ecoh_serotyper | ecoh_sequences.fasta（597 seqs） | O:H serotype |
| Shigella | shigella_serotyper | shigella_ref.fasta（95 seqs） | species + 58 种 serotype |

## SNP 管线（5 步）

```
步骤 1 · snp_calling（每株）
  raw FASTQ → bwa mem（vs LT2 参考）→ samtools sort → BAM

步骤 2 · joint_variant_calling（多样本联合）
  N 个 BAM → bcftools mpileup（联合）→ bcftools call → joint VCF
  ※ 联合 calling 保证跨样本基因型一致性

步骤 3 · snp_matrix（全基因组矩阵）
  joint VCF → Python 解析 → FASTA alignment
  策略：whole-genome mode（保留所有变异位点，缺失用 N 填充）

步骤 4 · phylo_tree（系统发育树）
  FASTA → IQ-TREE -m GTR -bb 1000 -alrt 1000
  输出：Newick treefile + IQ-TREE 报告

步骤 5 · snp_summary（距离矩阵）
  treefile + FASTA → JSON（Newick + pairwise distances + 统计）
```

### 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 变异检测策略 | **Joint calling**（非分别 call 后 merge） | 避免跨样本基因型不一致 |
| 矩阵策略 | **Whole-genome**（非 strict core） | 保留所有变异位点，N 填充缺失（4.7%），无信号丢失 |
| 对齐格式 | **FASTA**（非 PHYLIP） | 无 10 字符名称截断限制 |
| 参考基因组 | NC_003197.2（LT2, 4.8 Mb） | 仅染色体，排除质粒 |

### 验证结果（7 株 Salmonella）

| 指标 | 值 |
|---|---|
| SNP 位点数 | 122,598 |
| 缺失率 | 4.7% |
| Parsimony-informative sites | 55,437 |
| Bootstrap 支持 | 所有内部分支 ≥ 92% |
| TYP-001 ↔ TYP-002 距离 | 1,666 SNPs（最近，同血清型） |

## 管线参数

常用 Snakemake 配置：

| 参数 | 默认 | 位置 |
|---|---|---|
| Threads | 8 | `--cores` |
| Min contig length | 200 | assembly rule |
| invA identity threshold | 90% | species rule |
| invA coverage threshold | 80% | species rule |
| abricate min identity | 80% | amr rules |
| abricate min coverage | 80% | amr rules |
| SNP QUAL filter | 30 | snp_matrix script |
| IQ-TREE model | GTR + UFBoot 1000 | phylo_tree rule |

组装质量阈值（评估组装是否可用）：

| 指标 | Good | Acceptable | Poor |
|---|---|---|---|
| N50 | >100 kb | 10–100 kb | <10 kb |
| Total contigs | <100 | 100–500 | >500 |
| Total length | 4.5–5.5 Mb | 4–6 Mb | <4 或 >6 Mb |
| GC content | 50–53% | 48–55% | <48% 或 >55% |

完整参数与各步耗时见 `skills/run-pipeline/references/pipeline-params.md`。

## 触发方式

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

Snakemake 状态持久化在 `workflows/salmonella/.snakemake/`，中断后可断点续跑。若目录被锁：`cd workflows/salmonella && snakemake --unlock`。

更多故障处理见[故障排查](../reference/troubleshooting.md)。
