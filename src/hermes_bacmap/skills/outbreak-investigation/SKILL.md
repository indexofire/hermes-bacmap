---
name: outbreak-investigation
description: >
  Meta-skill orchestrating the AI-native outbreak investigation loop:
  define strain groups → differential gene enrichment → pan-genome novel
  cluster discovery → literature verification → validation recommendation →
  report. Chains bio_differential_genes, bio_pangenome,
  bio_analytics_query, and bio_lit_search into one auditable workflow.
  Load when user mentions outbreak investigation, 暴发调查, comparing strain
  groups, finding enriched/unique genes, novel marker discovery, or asks
  "what's special about these strains".
  Trigger words: 暴发, outbreak, enriched, 富集, 差异基因, novel marker,
  新标记, compare groups, investigate.
version: 0.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [bioinformatics, outbreak, pangenome, discovery, surveillance]
    category: bioinfo
    requires_toolsets: [terminal]
---

# Outbreak Investigation — Discovery Loop

## When to Use

- User has ≥2 groups of analyzed strains (e.g., outbreak vs background)
- Questions like "这些暴发株有什么特别的基因?" or "why are these strains different?"
- Goal: find genes/markers that distinguish the groups, verify against
  literature, and produce an auditable investigation report

## Prerequisites

- All strains analyzed (bio_analyze_pathogen) with annotation + gapit results
- ≥4 strains per group recommended for meaningful Fisher statistics
- Discovery layer available: bio_differential_genes, bio_pangenome,
  bio_analytics_query, bio_lit_search

## Procedure

### Stage 1 — Group definition

1. Confirm the two groups with the user explicitly (strain IDs, grouping rationale)
2. Verify analysis status: bio_list_samples → each strain needs
   `results/{sample}/annotation/annotation.json` and `results/{sample}/amr/gapit_*.tsv`
3. If strains are not analyzed, run bio_analyze_pathogen first

### Stage 2 — Known-gene enrichment

4. Run per source (report all three when files exist):
   - `bio_differential_genes(group_a=<outbreak>, group_b=<background>, source=gapit_vfdb)` — virulence
   - `... source=gapit_card` — AMR
   - `... source=gapit_plasmidfinder` — plasmids
5. Interpret: q_value < 0.05 and fold_enrichment ≥ 2 → strong candidates
6. Record hit table (gene, prevalence_a/b, q_value, fold) for the report

### Stage 3 — Novel cluster discovery

7. `bio_pangenome(samples=<all group strains>)` — clusters all CDS proteins
8. Query the matrix for group-specific novel clusters:
   `bio_analytics_query(sql="SELECT cluster_id, representative, named_gene,
   n_genomes FROM pangenome WHERE is_novel AND n_genomes >= 3 ORDER BY
   n_genomes DESC")` then cross-check per-sample columns for group specificity
9. Novel + recurring + group-specific = putative new marker candidates

### Stage 4 — Literature verification

10. For each top candidate (max 3-5, avoid API waste):
    `bio_lit_search(query="<gene or cluster context> <species> virulence")`
11. Classify: already-described (cite PMID) / partially-related / no prior
    evidence (true novelty claim)
12. Cite PMIDs in the report — never claim novelty without this check

### Stage 5 — Report

13. Structure (all numbers must come from tool outputs above):
    - Background: groups, sample counts, data sources
    - Known genes enriched: table with statistics
    - Novel clusters: representatives, prevalence, literature status
    - Interpretation: cautious claims, uncertainty stated
    - Recommended next steps: panel validation, marker registration
14. Every number in the report MUST trace to a tool result — do not compute
    or guess numbers yourself

## Guardrails

- Literature claims need PMID/DOI from bio_lit_search output
- Fisher results with n<4 per group: report as descriptive, not significant
- Novel cluster claims always state the clustering parameters (min_seq_id,
  coverage) — results depend on them
- Never claim clinical significance from gene presence alone

## References

- references/worked-example.md — full worked outbreak investigation example
