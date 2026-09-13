# 病原分析总览：流程、能力与实现

本文是 4 种食源性病原分析的**实现级总览**：完整的分析流程 DAG、每种病原的能力矩阵与具体实现方式（rule → 工具 → 代码模块 → 数据库 → 输出）。各病原的生物学背景与结果判读见分论：

- [Salmonella](salmonella.md) · [DEC / E. coli](dec.md) · [Shigella / EIEC](shigella.md) · [V. parahaemolyticus](vpara.md)

---

## 1. 分析流程全景

### 1.1 单样本主流程（per-sample DAG）

所有病原共用一条主流程，入口 `workflows/bacmap/Snakefile`，`rule all` 的目标为每株的 `{sample}_summary.json` + `annotation.json` + `vpa_serotype.json`（+ cohort 汇总）。

| # | Rule（文件） | 工具 | 输入 → 输出 | 说明 |
|---|---|---|---|---|
| 1 | `qc_fastp`（qc.smk） | fastp | raw FASTQ → clean FASTQ（temp）+ fastp.json/html | Q20 过滤、长度 ≥50、自动接头检测 |
| 2 | `assembly_shovill`（assembly.smk） | Shovill（SPAdes） | clean FASTQ → contigs.fasta | minlen 500 / ram 8 / depth 100 |
| 3 | `assembly_stats`（assembly.smk） | seqkit stats | contigs → assembly_stats.tsv | 组装质量统计 |
| 4 | `species_identify`（species.smk） | Python `species_identifier` + BLAST | contigs → species_id.json | 5 marker 基因 1 次 BLAST，按结果路由（见 §2） |
| 5 | `taxonomy_validation`（taxonomy.smk） | Python `taxonomic_validator` | contigs → validation.json | simple 模式（marker）/ standard 模式（CheckM2 完整度+污染度、GTDB-Tk 分类） |
| 6 | `genome_annotation`（annotation.smk） | pyrodigal + blastp（Prokka DBs） | contigs → annotation.json | 纯 Python CDS 预测 + sprot/amr/is 注释 |
| 7 | `typing_mlst`（typing_amr.smk） | gmlst | contigs → mlst.tsv | 经典 7-gene MLST，scheme 按物种自动选择 |
| 8 | `typing_sistr`（typing_amr.smk） | SISTR | contigs → sistr.json + sistr_cgmlst.csv | Salmonella 血清型（含 mash + cgMLST 分型） |
| 9 | `amr_abricate_vfdb`（typing_amr.smk） | abricate | contigs → abricate_vfdb.tsv | 毒力基因（minid 80 / mincov 60） |
| 10 | `amr_abricate_card`（typing_amr.smk） | abricate | contigs → abricate_card.tsv | AMR 耐药基因 |
| 11 | `amr_abricate_plasmidfinder`（typing_amr.smk） | abricate | contigs → abricate_plasmidfinder.tsv | 质粒复制子 |
| 12 | `amr_amrfinderplus`（typing_amr.smk） | NCBI AMRFinderPlus | contigs → amrfinderplus.tsv | 按物种加 `--organism`（见 §3.6） |
| 13 | `dec_ecoh_serotype` / `dec_pathotype` / `shigella_serotype`（dec_shigella.smk） | Python `typing/` 模块 | contigs / vfdb → ecoh_serotype.json / pathotype.tsv / shigella_serotype.json | DEC 与 Shigella 专属（见 §4.2/§4.3） |
| 14 | `vpara_targets` / `vpara_virulence` / `vpara_serotype`（vpara.smk） | blastn + Python `typing/` 模块 | contigs → targets_blastn.tsv / virulence.json / vpa_serotype.json | V. parahaemolyticus 专属（见 §4.4） |
| 15 | `report_summary`（report.smk） | `scripts/collect_summary.py` | 上述 15 个产物 → `{sample}_summary.json` | 聚合为单一 JSON，是入库（GOM）与报告的数据源 |

### 1.2 物种路由机制

**没有独立的路由 rule**——路由内嵌在两处：

1. **样本表预声明**：`config/samples.tsv` 的 `species` 列（`Salmonella` / `E.coli` / `Shigella` / `V.parahaemolyticus`）决定 MLST scheme、AMRFinderPlus organism、SNP 分组等所有 `lambda wc:` 参数选择。
2. **组装后验证**：`species_identify` 用 5 个 marker 基因对 `species_markers` 数据库做**一次** BLAST（identity ≥85%、coverage ≥30%），按优先级 `invA > ipaH > toxR > tlh > uidA` 取第一个命中判物种（`analysis/species_identifier.py`），与样本表声明互为印证。
   加新病原只需向 `markers.fasta` 加基因 + 在 `_GENE_TO_SPECIES` 注册，无需改 rule。

### 1.3 cohort SNP 流程（同物种 ≥2 株自动触发）

`snp.smk` 按物种分三组，各组独立产出系统发育：

| 分组 | 参考基因组 | 覆盖物种 |
|---|---|---|
| `salmonella` | *S. enterica* LT2（salmonella_LT2.fasta） | Salmonella |
| `ecoli` | *E. coli* K-12 MG1655（ecoli_k12.fasta） | E.coli + Shigella（分类学同种，共用参考） |
| `vpara` | RIMD 2210633（vpara_rimd.fasta） | V.parahaemolyticus |

流程：`snp_calling`（bwa mem -Y -M + samtools sort → BAM）→ `joint_variant_calling`（bcftools mpileup -q20 -Q20 --max-depth 200 | call -mv --ploidy 1，组内联合呼叫）→ `snp_matrix`（VCF → core_snps.fasta 全基因组 SNP 矩阵）
→ `phylo_tree`（IQ-TREE GTR；≥4 株时 -bb 1000 -alrt 1000 UltraFast Bootstrap）→ `snp_summary`（距离矩阵 + Newick → snp_summary.json）。

### 1.4 cgMLST 溯源流程（默认关闭，opt-in）

`cgmlst.smk`，由 `config.cgmlst.run_cgmlst_cohort: true` 开启（默认 false 时 4 个 cohort rule **不进入 DAG**）：

- `typing_cgmlst`（常开）：gmlst 对 EnteroBase cgMLST scheme 分型——senterica_2（3002 loci）/ ecoli_2（2513）/ vparahaemolyticus_3（2254）。
- cohort 链：`cgmlst_cohort_profiles`（合并组内 per-sample TSV）→ `cgmlst_distance_matrix`（Hamming 等位基因距离：**只在双方都有 call 的 loci 上计数**，任一方缺失即排除，EnteroBase HierCC 约定）
  → `cgmlst_mst`（GrapeTree 式最小生成树，scipy；可选 nj）→ `cgmlst_summary`。
- **溯源投影**：`analysis/cgmlst_projection.py` 将查询株与本地参考库比对，取 Hamming 距离最近 top 10，按 per-species 发表阈值输出 `OUTBREAK / RELATED / UNRELATED / UNDETERMINED` 判定（阈值与文献来源见 §5.2）。

### 1.5 容错设计

判定类 rule 全部带 fallback（`|| echo '<占位 JSON>' > 输出`）：物种、MLST、SISTR、ecoh/shigella/vpa 血清型、taxonomy、amrfinderplus（`|| touch`）失败时写入结构化占位结果而非中断管线——保证 `report_summary` 的 15 个输入永远齐备，单步失败可后补重跑（Snakemake 断点续跑）。
abricate 与组装类 rule 无 fallback（失败即失败，属硬错误）。

---

## 2. 四病原能力矩阵

| 能力 | Salmonella | DEC（E. coli） | Shigella / EIEC | V. parahaemolyticus |
|---|---|---|---|---|
| 物种鉴定 marker | invA | uidA | ipaH | toxR + tlh |
| 标准分类验证 | GTDB-Tk / CheckM2（standard 模式） | 同左 | 同左 | 同左 |
| 血清型 | **SISTR**（serovar/serogroup/O/H） | **ecoh_serotyper**（O:H，Python） | **shigella_serotyper**（58 型，Python） | **VpaSerotyper**（O/K，Python） |
| Pathotype | — | **call_pathotype**（STEC/EPEC/ETEC/EIEC/EAEC） | EIEC 标记提示（EclacY + ipaH） | — |
| MLST（经典） | salmonella_2 | ecoli_1 | ecoli_1 | vparahaemolyticus_1 |
| cgMLST | senterica_2 | ecoli_2 | ecoli_2 | vparahaemolyticus_3 |
| AMR | abricate CARD + AMRFinderPlus（--organism Salmonella） | abricate CARD + AMRFinderPlus（--organism Escherichia） | 同 DEC | abricate CARD + AMRFinderPlus（无 organism） |
| 毒力 | abricate VFDB | abricate VFDB（兼作 pathotype 输入） | abricate VFDB | abricate VFDB + **tdh/trh 专项 BLAST** |
| 质粒 | abricate PlasmidFinder | 同左 | 同左 | 同左 |
| SNP/系统发育 | bwa+bcftools+iqtree vs LT2 | vs K-12（与 Shigella 同组） | vs K-12（与 E.coli 同组） | vs RIMD |
| cgMLST 溯源阈值 | 10/3/50（有发表值） | 5/50 + 血清型特异 | 5/50（sonnei 需 SNV 确认） | **无发表值 → UNDETERMINED** |
| 注释 | pyrodigal + Prokka DBs | 同左 | 同左 | 同左 |

---

## 3. 通用能力实现细节（4 病原共享）

### 3.1 质控与组装

fastp 参数取自 `config.yaml:tools.fastp`；Shovill 封装 SPAdes 并自带 read correction 与 contig 过滤。clean reads 标记 `temp`——SNP calling 完成后自动删除，contigs.fasta 是后续所有基于组装的分析的唯一输入。

### 3.2 物种鉴定（`analysis/species_identifier.py`）

`identify(contigs)` 委托 `gene_scanner.scan(db_name="species_markers")`（底层走 engine.SequenceMatcher → blastn 后端），每个 marker 取最佳 hit，按 `_SPECIES_PRIORITY` 排序输出 `detected_markers` 并判定 species + confidence。
阈值：identity ≥85%、coverage ≥30%（宽松——因为 marker 基因高度保守，宽进严出靠优先级裁决）。

### 3.3 分类学验证（`analysis/taxonomic_validator.py`）

`validate_genome(contigs, mode)`：`simple` 模式仅做 marker 鉴定；`standard` 模式追加 CheckM2（completeness/contamination，需 `CHECKM2DB` 环境变量）与 GTDB-Tk（分类学归属，需 GTDB 数据库）。工具或数据库缺失时降级为 skip 并写明原因，不失败。

### 3.4 基因组注释（`analysis/genome_annotator.py`）

pyrodigal 做 CDS 预测（与 Prodigal 100% 等价），blastp 对 Prokka 三库（sprot/amr/is）注释，替代 Perl 依赖沉重的 Prokka CLI。输出 annotation.json（CDS + 注释 + 统计）。

### 3.5 MLST（`typing_mlst`）

gmlst 一次调用完成分型，scheme 由样本表 species 映射（`_GMLST_SCHEMES`）：Salmonella→salmonella_2、E.coli/Shigella→ecoli_1、V.para→vparahaemolyticus_1。失败写 `ST=N/A` 占位。

### 3.6 AMR / 毒力 / 质粒（abricate ×3 + AMRFinderPlus）

- abricate 三库统一参数：`--minid 80 --mincov 60`（config 可调）。CARD=耐药、VFDB=毒力、PlasmidFinder=质粒复制子。
- AMRFinderPlus 按物种加 organism 标志（Salmonella→`--organism Salmonella`，E.coli/Shigella→`--organism Escherichia`，V.para 不加——无官方 organism 库），`--coverage_min 0.5`，数据库取 `data/db/amrfinderplus` 下最新版本目录。

### 3.7 通用基因扫描引擎（`analysis/gene_scanner.py` + `engine/`）

所有 Python 判定模块（物种/ecoh/shigella）不直接调 BLAST，而是委托 gene_scanner → engine.SequenceMatcher（自动后端选择：小文件 blastn、>10MB minimap2；蛋白 blastp）。
数据库按名注册（`species_markers` / `ecoh` / `shigella_ref` / ...），对应 `data/reference/` 下的 FASTA。这是"换后端不改业务代码"的抽象层。

---

## 4. 病原特异性实现

### 4.1 Salmonella

| 项 | 实现 |
|---|---|
| 物种 | invA marker（优先级第 1） |
| 血清型 | SISTR：`sistr -MM --more-results --run-mash`，输出 serovar / serogroup / o_antigen / h1 / h2 + cgMLST 分型 CSV，SISTR 自带 mash 物种复核 |
| MLST | salmonella_2（aroC/dnaN/hemD/hisD/purE/sucA/thrA） |
| AMR | 双引擎：abricate CARD + AMRFinderPlus（organism 特异，含点突变耐药） |
| SNP | vs LT2（NC_003197.2） |

### 4.2 DEC（致泻性大肠埃希菌）

| 项 | 实现 |
|---|---|
| 物种 | uidA marker |
| 血清型 | `typing/ecoh_serotyper.py`：扫描 ecoh 库，正则解析 O 抗原基因（wzx/wzy/wzm/wzt-O*n*）与 H 抗原基因（fliC/flkA/fllA/flmA/flnA-H*n*），每抗原型打分 `identity × coverage / 100` 取最高 → `O{n}:H{n}`。无 O 抗原输出 `-`（如 O157 STEC 常见丢失） |
| **Pathotype** | `scripts/call_pathotype.py`，输入为 vfdb 结果，规则按声明顺序可**多重命中**：stx1/stx2→STEC；ipaH 族（ipaH/ipaB/ipaC/ipaD/ipaJ/ipgC/mxi 等）→EIEC/Shigella；eae+bfpA（all）→tEPEC；eae→aEPEC；est/elt/STh/STp/LT→ETEC；aggR/aatA/aaiC→EAEC；全阴→Non-pathogenic |
| MLST | ecoli_1；SNP 与 Shigella 同组（K-12 参考） |

### 4.3 Shigella / EIEC

| 项 | 实现 |
|---|---|
| 物种 | ipaH marker（多拷贝，灵敏度最高） |
| 血清型 | `typing/shigella_serotyper.py`（移植 CFSAN ShigATyper，58 型），扫 shigella_ref 库后按基因组合判定：<br>· *S. flexneri*：Sf6_wzx→6 型；gtr 基因组合（gtrI/II/IV/V/X/IC + Oac/Oac1b + Xv）**精确匹配**→high；Oac 变体→medium；差 1 基因的近似匹配→medium；有 Sf_wzx/wzy 无 gtr→Y 型；组合未知→"novel serotype"（low）<br>· *S. sonnei*：Ss_wzx+wzy 双阳→high<br>· *S. dysenteriae* 1–15 / *S. boydii* 1–20：wzx+wzy 双阳→high，单阳→medium，SdProv/SbProv→不可分型<br>· 多物种信号同时出现→疑似污染/组装错误（low）<br>· **EIEC 鉴别提示**：检出 EclacY（E. coli 标记）+ ipaH → 标注 "may be EIEC rather than Shigella" |
| 与 DEC 的关系 | ipaH 阳性的样本同时跑 ecoh_serotyper + pathotype（EIEC/Shigella pathotype），三条证据合并判读 |

### 4.4 V. parahaemolyticus

| 项 | 实现 |
|---|---|
| 物种 | `vpara_targets`：独立 BLAST（evalue 1e-50、word_size 28）对 vpara_targets 库，三态判定——有 hit 且含 toxR/tlh → `V_parahaemolyticus`；有 hit 无 toxR/tlh → `ambiguous_vpara`；无 hit → `not_V_parahaemolyticus`（写入 species_verdict.txt） |
| 毒力 | `vpara_virulence`：tdh/trh/tlh 逐基因 BLAST → 布尔 virulence.json（tdh+trh 组合判读见 [vpara.md](vpara.md)） |
| 血清型 | `typing/vpa_serotyper.py` + `vpa_serotyper_engine.py`（移植 vpautils，Kaptive 式四阶段）：<br>A. minimap2（mappy）从 contigs 提取 locus 区域 → B. sourmash MinHash containment 排序候选 O/K locus（>30%）→ C. 逐基因覆盖度/一致性验证 → D. 规则引擎出置信度（Perfect/High/Medium/Low/Unknown），报告缺失基因与警报。默认 `OUT:KUT`（不可分型）<br>数据库：`data/reference/vpa_serotype/`（gene_refs + ref_seqs + ref_meta.pkl + CPS/O 抗原 GenBank） |
| 溯源 | cgMLST scheme vparahaemolyticus_3 可跑，但**无发表暴发阈值** → 溯源判定恒为 UNDETERMINED（需本地标定，见 §5.2） |

---

## 5. 输出产物与参数速查

### 5.1 结果目录结构

```
results/
├── {sample}/
│   ├── qc/            fastp.json / fastp.html（clean reads 为 temp）
│   ├── assembly/      contigs.fasta / assembly_stats.tsv
│   ├── species/       species_id.json
│   ├── taxonomy/      validation.json
│   ├── annotation/    annotation.json
│   ├── typing/        mlst.tsv / sistr.json / sistr_cgmlst.csv / cgmlst.tsv
│   ├── amr/           abricate_card.tsv / abricate_vfdb.tsv / amrfinderplus.tsv
│   ├── plasmid/       abricate_plasmidfinder.tsv
│   ├── dec/           ecoh_serotype.json / pathotype.tsv / shigella_serotype.json
│   ├── vpara/         targets_blastn.tsv / species_verdict.txt / virulence.json
│   ├── vpa/           vpa_serotype.json
│   ├── snp/           snps.bam
│   └── report/        {sample}_summary.json          ← GOM 入库 + HTML 报告数据源
├── snp/{group}/       joint.vcf.gz / core_snps.fasta / core.treefile / snp_summary.json
└── cgmlst/{group}/    cgmlst_profiles.tsv / distance_matrix.json / core.treefile / cgmlst_summary.json
```

### 5.2 cgMLST 溯源阈值（config.yaml，均有文献来源）

| 物种 | outbreak | clonal | related | 来源 |
|---|---|---|---|---|
| Salmonella | ≤10 | ≤3 | ≤50 | Zhou 2020 Genome Res（HC5/HC10、HC50）；Ferrato 2023（ST11/ST34） |
| E.coli | ≤5 | —（血清型特异：O26:H11=8 / O157:H7=16 / O103:H2=5 / O80:H2=9） | ≤50 | Emerjean 2025 CDC EID；Zhou 2020 |
| Shigella | ≤5 | — | ≤50 | Hawkey 2021 Nat Commun；**S. sonnei 需 SNV 确认** |
| V. parahaemolyticus | null | — | null | 无发表阈值（Achtman 2022 仅 HC1090 物种边界）→ UNDETERMINED |

距离定义：双方均非缺失的 loci 上等位基因差异数（HierCC 约定）。

### 5.3 关键工具参数（config.yaml）

| 工具 | 参数 |
|---|---|
| fastp | qualified_quality_phred=20, length_required=50, detect_adapter_for_pe |
| Shovill | minlen=500, ram=8, depth=100 |
| abricate | minid=80, mincov=60 |
| AMRFinderPlus | coverage_min=0.5, organism 按物种 |
| blastn（vpara 专项） | evalue=1e-50, word_size=28 |
| bcftools mpileup | -q 20 -Q 20 --max-depth 200 |
| IQ-TREE | -m GTR；≥4 株加 -bb 1000 -alrt 1000 |

---

## 6. AI 层调用入口

分析能力通过 27 个 Hermes tools 暴露给 LLM（表驱动注册于 `tools/registry.py`），与分析直接相关的包括：

| Tool | 作用 |
|---|---|
| `bio_analyze_pathogen` | 端到端编排（等价 `scripts/run_analysis.py --sample`） |
| `bio_get_result` / `bio_verify_result` | 读 summary / 确定性规则校验（三层防御 Layer 2） |
| `bio_gene_scan` | 任意参考库基因扫描（gene_scanner 直通） |
| `bio_snp_tree` / `bio_cgmlst` | cohort SNP / cgMLST 溯源查询 |
| `bio_vpa_serotype` | V. para 血清型独立调用 |
| `bio_validate_taxonomy` / `bio_annotate` | 分类验证 / 注释 |
| `bio_search_samples` / `bio_query_metadata` | GOM 检索（FTS5） |
| `bio_generate_report` / `bio_diagnose` |
| `bio_species_compare` | 跨方法物种鉴定一致性矩阵 + 仲裁结论 | HTML/PDF 报告 / 失败诊断（9 种错误模式） |

---

*实现对应版本：V0.7（2026-09）。规则计数：11 个 rule 文件 / 29 rules（25 常规 + 4 cgMLST cohort 门控）+ `rule all`。*
