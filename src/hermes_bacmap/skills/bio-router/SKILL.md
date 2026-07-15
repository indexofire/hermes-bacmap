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
