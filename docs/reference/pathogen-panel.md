# 病原面板数据库台账（refseq_panel）

- 候选病原：[NCBI Pathogen Detection 追踪组](http://ftp.ncbi.nlm.nih.gov/pathogen/Results)，构建时活清单对账。
- 选择规则：每物种（species_taxid）reference 必选 + complete ≤5（representative 优先），共 **2495 株**（reference 391 + complete 2104）。

机器可读台账（本地，随库分发）：`data/db/refseq_panel/tracked_pathogens.tsv`、`panel_accessions.tsv`（全量 accession）；skani 库 `panel.sketch`。

| 追踪组 | species taxid | reference | complete | 合计 |
|---|---|---|---|---|
| Acinetobacter | 260 个物种 taxid（全表见 TSV） | 104 | 290 | 394 |
| Aeromonas | 124 个物种 taxid（全表见 TSV） | 35 | 145 | 180 |
| Aeromonas_salmonicida | 645 | 1 | 5 | 6 |
| Aeromonas_sobria | 646 | 1 | 0 | 1 |
| Aeromonas_veronii | 654 | 1 | 5 | 6 |
| Bacillus_cereus_group | 3041344;3094884;3445632 | 0 | 3 | 3 |
| Bacillus_inaquosorum | 483913 | 1 | 5 | 6 |
| Burkholderia_cepacia_complex | 3707424 | 0 | 2 | 2 |
| Burkholderia_mallei | 13373 | 1 | 5 | 6 |
| Campylobacter | 85 个物种 taxid（全表见 TSV） | 55 | 100 | 155 |
| Citrobacter_freundii | 2066049;2077147;2077148;2077149;546 | 1 | 9 | 10 |
| Citrobacter_portucalensis | 1639133 | 1 | 5 | 6 |
| Clostridioides_difficile | 1496 | 1 | 5 | 6 |
| Clostridium_botulinum | 1491 | 1 | 5 | 6 |
| Clostridium_perfringens | 1502 | 1 | 5 | 6 |
| Corynebacterium_striatum | 43770 | 1 | 5 | 6 |
| Cronobacter | 34 个物种 taxid（全表见 TSV） | 7 | 50 | 57 |
| Edwardsiella_ictaluri | 67780 | 1 | 5 | 6 |
| Edwardsiella_piscicida | 1263550 | 1 | 5 | 6 |
| Edwardsiella_tarda | 636 | 1 | 5 | 6 |
| Elizabethkingia | 12 个物种 taxid（全表见 TSV） | 7 | 21 | 28 |
| Enterobacter_asburiae | 61645 | 1 | 5 | 6 |
| Enterobacter_bugandensis | 881260 | 1 | 5 | 6 |
| Enterobacter_cancerogenus | 69218 | 1 | 5 | 6 |
| Enterobacter_chengduensis | 2494701 | 1 | 3 | 4 |
| Enterobacter_chuandaensis | 2497875 | 1 | 2 | 3 |
| Enterobacter_cloacae | 20 个物种 taxid（全表见 TSV） | 1 | 24 | 25 |
| Enterobacter_hormaechei | 158836 | 1 | 5 | 6 |
| Enterobacter_intestinihominis | 3133180 | 1 | 4 | 5 |
| Enterobacter_kobei | 208224 | 1 | 5 | 6 |
| Enterobacter_ludwigii | 299767 | 1 | 5 | 6 |
| Enterobacter_mori | 539813 | 1 | 5 | 6 |
| Enterobacter_oligotrophicus | 2478464 | 1 | 1 | 2 |
| Enterobacter_quasiroggenkampii | 2497436 | 1 | 3 | 4 |
| Enterobacter_roggenkampii | 1812935 | 1 | 5 | 6 |
| Enterobacter_sichuanensis | 2071710 | 1 | 5 | 6 |
| Enterobacter_soli | 885040 | 1 | 4 | 5 |
| Enterococcus_faecalis | 1351 | 1 | 5 | 6 |
| Enterococcus_faecium | 1352 | 1 | 5 | 6 |
| Enterococcus_hirae | 1354 | 1 | 5 | 6 |
| Escherichia_coli_Shigella | 62 个物种 taxid（全表见 TSV） | 6 | 83 | 89 |
| Flavobacterium_psychrophilum | 96345 | 1 | 5 | 6 |
| Haemophilus_influenzae | 727 | 1 | 5 | 6 |
| Klebsiella | 304 个物种 taxid（全表见 TSV） | 18 | 347 | 365 |
| Klebsiella_oxytoca | 571 | 1 | 5 | 6 |
| Kluyvera_intermedia | 61648 | 1 | 5 | 6 |
| Kosakonia_oryzendophytica | 1005665 | 1 | 0 | 1 |
| Kosakonia_oryziphila | 1005667 | 1 | 0 | 1 |
| Legionella_anisa | 28082 | 1 | 5 | 6 |
| Legionella_bozemanae | 447 | 1 | 0 | 1 |
| Legionella_cherrii | 28084 | 1 | 1 | 2 |
| Legionella_feeleii | 453 | 1 | 0 | 1 |
| Legionella_pneumophila | 446 | 1 | 5 | 6 |
| Listeria | 56 个物种 taxid（全表见 TSV） | 22 | 56 | 78 |
| Listeria_innocua | 1642 | 1 | 5 | 6 |
| Mannheimia_haemolytica | 75985 | 1 | 5 | 6 |
| Morganella | 2733648;2733649;2955964;368603;582 | 2 | 10 | 12 |
| Mycobacterium_tuberculosis | 1773;2583589;2583590;2583591;2583592;2583593;2583631 | 1 | 11 | 12 |
| Neisseria_bacilliformis | 267212 | 1 | 0 | 1 |
| Neisseria_cinerea | 483 | 1 | 1 | 2 |
| Neisseria_elongata | 495 | 1 | 4 | 5 |
| Neisseria_flava | — | 0 | 0 | 0 |
| Neisseria_gonorrhoeae | 485 | 1 | 5 | 6 |
| Neisseria_lactamica | 486 | 1 | 3 | 4 |
| Neisseria_meningitidis | 487 | 1 | 5 | 6 |
| Neisseria_oralis | 1107316 | 1 | 0 | 1 |
| Neisseria_perflava | 33053 | 1 | 2 | 3 |
| Neisseria_polysaccharea | 489 | 1 | 1 | 2 |
| Neisseria_subflava | 28449 | 1 | 5 | 6 |
| Neisseria_weaveri | 28091 | 1 | 1 | 2 |
| Pasteurella_multocida | 747 | 1 | 5 | 6 |
| Photobacterium_damselae | 38293 | 1 | 5 | 6 |
| Phytobacter_massiliensis | 1485952 | 1 | 0 | 1 |
| Pluralibacter_gergoviae | 61647 | 1 | 3 | 4 |
| Providencia | 75 个物种 taxid（全表见 TSV） | 17 | 95 | 112 |
| Pseudomonas_aeruginosa | 287 | 1 | 5 | 6 |
| Pseudomonas_putida | 303;3122582 | 1 | 6 | 7 |
| Salmonella | 345 个物种 taxid（全表见 TSV） | 2 | 355 | 357 |
| Serratia | 100 个物种 taxid（全表见 TSV） | 25 | 140 | 165 |
| Shewanella_algae | 38313 | 1 | 5 | 6 |
| Staphylococcus_aureus | 1280;2560781 | 1 | 6 | 7 |
| Staphylococcus_pseudintermedius | 283734 | 1 | 5 | 6 |
| Stenotrophomonas_maltophilia | 3060303;3454438;3456024;3459469;40324 | 1 | 9 | 10 |
| Streptococcus_agalactiae | 1311 | 1 | 5 | 6 |
| Streptococcus_equi | 1335;1336 | 2 | 10 | 12 |
| Streptococcus_iniae | 1346 | 1 | 5 | 6 |
| Streptococcus_mutans | 1309 | 1 | 5 | 6 |
| Streptococcus_pneumoniae | 1313 | 1 | 5 | 6 |
| Streptococcus_pyogenes | 1314 | 1 | 5 | 6 |
| Streptococcus_suis | 1307 | 1 | 5 | 6 |
| Treponema_pallidum | 160 | 1 | 5 | 6 |
| Vibrio_alginolyticus | 663 | 1 | 5 | 6 |
| Vibrio_antiquarius | 150340 | 1 | 0 | 1 |
| Vibrio_cholerae | 666 | 1 | 5 | 6 |
| Vibrio_diabolicus | 50719 | 1 | 5 | 6 |
| Vibrio_fluvialis | 676 | 1 | 5 | 6 |
| Vibrio_harveyi | 669 | 1 | 5 | 6 |
| Vibrio_metoecus | 1481663 | 1 | 4 | 5 |
| Vibrio_metschnikovii | 28172 | 1 | 5 | 6 |
| Vibrio_mimicus | 674 | 1 | 5 | 6 |
| Vibrio_owensii | 696485 | 1 | 5 | 6 |
| Vibrio_parahaemolyticus | 670 | 1 | 5 | 6 |
| Vibrio_vulnificus | 672 | 1 | 5 | 6 |
| Yersinia_enterocolitica | 630 | 1 | 5 | 6 |
| Yersinia_ruckeri | 29486 | 1 | 5 | 6 |

