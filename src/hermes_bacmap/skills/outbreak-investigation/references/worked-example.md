# Worked Example — Outbreak Investigation

Scenario: 12 outbreak strains (SAM-OUT-001..012) vs 8 background strains
(SAM-BG-001..008), all V. parahaemolyticus, all analyzed.

## Stage 1 — Group definition

```
User: 调查这批暴发株，和往年背景株比较有什么特别的
Agent: 确认分组 — 暴发组 SAM-OUT-001..012 (2026-08)，背景组 SAM-BG-001..008 (2024-2026)
       → bio_list_samples 确认 20 株均有 annotation + gapit 结果 ✓
```

## Stage 2 — Known-gene enrichment

```
bio_differential_genes(
  group_a=["SAM-OUT-001", ..., "SAM-OUT-012"],
  group_b=["SAM-BG-001", ..., "SAM-BG-008"],
  source="gapit_vfdb")
```

Result (excerpt):

| gene | prevalence_a | prevalence_b | fold | p_value | q_value |
|---|---|---|---|---|---|
| tdh | 1.000 (12/12) | 0.125 (1/8) | 8.0 | 0.0003 | 0.004 |
| T3SS2 | 1.000 (12/12) | 0.250 (2/8) | 4.0 | 0.002 | 0.018 |

→ tdh + T3SS2 strongly enriched in outbreak group (q < 0.05).

## Stage 3 — Novel cluster discovery

```
bio_pangenome(samples=[20 株全部])
→ total_clusters=3847, novel_clusters=412, matrix: pangenome/presence_matrix.parquet
```

```
bio_analytics_query(sql="""
  SELECT cluster_id, representative, n_genomes,
         SUM("SAM-OUT-001"+"SAM-OUT-002") AS out_pres  -- simplified
  FROM pangenome WHERE is_novel AND n_genomes >= 5
  ORDER BY n_genomes DESC""")
```

Result: cluster_0042 (rep: SAM-OUT-003__cds1187, 11/12 outbreak, 0/8
background, no named gene in any member) → putative novel marker.

## Stage 4 — Literature verification

```
bio_lit_search(query="Vibrio parahaemolyticus novel virulence island tdh T3SS2")
```

Result: 3 hits, tdh/T3SS2 well described (PMID:42551606 etc.);
cluster_0042 representative protein has no literature match →
"no prior evidence; putative novel element, warranting panel validation".

## Stage 5 — Report skeleton

- Background: 12 outbreak (2026-08) vs 8 background (2024-2026), same species
- Known genes: tdh 12/12 vs 1/8 (q=0.004), T3SS2 12/12 vs 2/8 (q=0.018)
- Novel: cluster_0042 present 11/12 vs 0/8, unnamed, cluster params 0.90/0.80
- Interpretation: outbreak strains carry tdh+ T3SS2+ profile plus one
  putative novel element; clinical significance requires validation
- Next: validate cluster_0042 against the 284-genome curated panel; if
  specific, register as custom gapit database

## Failure modes

- Group with <4 strains → descriptive statistics only
- No pangenome view → run bio_pangenome before analytics_query
- Literature search empty → try species + generic term before claiming novelty
