---
name: bio-router
description: >
  Bioinformatics skill router for hermes-bacmap. Load this FIRST when user
  asks about pathogen analysis, genome annotation, serotyping, MLST, AMR,
  SNP, phylogenetics, outbreak investigation, or sample search. Lists all
  available bioinformatics skills with trigger conditions and tool bindings.
version: 0.1.0
metadata:
  hermes:
    category: bioinfo
    tags: [bioinformatics, router, pathogen, genome-analysis]
---

# Bioinformatics Skill Router

This is the entry point for all bioinformatics tasks in hermes-bacmap.
Load the appropriate skill below based on what the user needs.

## Skill Catalog

| Skill | Load Command | When to Use |
|---|---|---|
| **run-pipeline** | `skill_view("hermes_bacmap:run-pipeline")` | Running pathogen WGS pipeline (QC → assembly → species → MLST → serotype → AMR → SNP → report). Supports Salmonella, DEC, Shigella, V. para. |
| **interpret-results** | `skill_view("hermes_bacmap:interpret-results")` | Interpreting any result: "what does ST19 mean?", "is blaCTX-M dangerous?", "are these 2 samples related?" |
| **bioinfo-analysis** | `skill_view("hermes_bacmap:bioinfo-analysis")` | Planning a new type of analysis not covered by the pipeline (e.g., long-read, RNA-seq) |

## Decision Tree

```
User says...
│
├── "分析 / analyze" + sample name
│   → Call tool: bio_analyze_pathogen
│   → Load skill: hermes_bacmap:run-pipeline (for pipeline details)
│
├── "注释 / annotate" + contigs
│   → Call tool: bio_annotate
│   → Load skill: hermes_bacmap:interpret-results (for gene function explanation)
│
├── "结果是什么 / what does X mean"
│   → Load skill: hermes_bacmap:interpret-results
│   → Use knowledge base to explain serotype/MLST/AMR/SNP
│
├── "比较 / compare" + samples
│   → Call tool: bio_snp_tree
│   → Load skill: hermes_bacmap:interpret-results (for SNP distance thresholds)
│
├── "搜索 / search / 找" + gene name / serotype
│   → Call tool: bio_search_samples
│
├── "系统发育树 / phylogenetic tree"
│   → Call tool: bio_snp_tree
│   → Load skill: hermes_bacmap:interpret-results
│
├── "报告 / report" + sample name
│   → Call tool: bio_generate_report
│
├── "列出样本 / list samples"
│   → Call tool: bio_list_samples
│
└── 其他生信分析（非管线）
    → Load skill: hermes_bacmap:bioinfo-analysis
```

## Tool Quick Reference

| Tool | Purpose |
|---|---|
| `bio_analyze_pathogen` | Run Snakemake pipeline |
| `bio_annotate` | Genome annotation (pyrodigal + Prokka DBs) |
| `bio_get_result` | Retrieve sample summary |
| `bio_verify_result` | Deterministic verification |
| `bio_generate_report` | HTML report generation |
| `bio_list_samples` | Sample inventory + status |
| `bio_gene_scan` | Multi-DB gene scanning |
| `bio_snp_tree` | Phylogenetic tree + distances |
| `bio_search_samples` | Natural language sample search |

## Supported Pathogens

| Pathogen | Species ID | Serotyping | MLST | AMR | SNP |
|---|---|---|---|---|---|
| **Salmonella** | invA | SISTR | gmlst | abricate (CARD/VFDB/PlasmidFinder) | ✅ bwa+bcftools+iqtree |
| **E. coli / DEC** | uidA | ecoh_serotyper | gmlst | abricate | — |
| **Shigella / EIEC** | ipaH | shigella_serotyper (58 types) | gmlst | abricate | — |
| **V. parahaemolyticus** | toxR+tlh | — | — | abricate | — |

## 物种鉴定模式选择（species-id 多方法）

用户希望启用更可靠的物种鉴定（ANI/sourmash/GTDB-Tk）时，指引部署对应数据库：

1. 先问需求档位并告知体积：
   - instant（159MB，快速预筛）/ mini（1-2GB，离线秒级真 ANI，推荐）
   - sourmash（3.7GB，含混合样本分解）/ full（30GB，全 GTDB 物种）/ standard（101GB+140GB RAM，仲裁）
2. 直接调用工具 `bio_db_setup`（action=list 展示档位 → action=run tier=<档位> 后台部署），用 `bio_db_status` 跟进进度；CLI 用户等价入口 `pixi run setup`
3. 部署完成后启用：`run_analysis.py --species-mode panel`（或改 config.yaml species_mode）
4. 库缺失时管线自动降级 marker 并 WARNING——遇到降级提示即指引上述部署流程
5. 多方法结果用 `bio_species_compare` 查看一致性矩阵与仲裁结论
