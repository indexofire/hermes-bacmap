# Salmonella Gold Standard 数据字典

每株样本的字段定义、格式、来源要求。

## 字段清单

### 标识（5 字段）

| 字段 | 类型 | 格式 | 示例 | 必填 |
|---|---|---|---|---|
| `strain_id` | str | `SAM-{TYP}-NNN`（本地编号） | `SAM-TYP-001` | ✅ |
| `biosample_accession` | str | `SAMN\d+`（NCBI BioSample） | `SAMN02603071` | ✅ |
| `sra_accession` | str | `SRR\d+`（SRA Run，Illumina PE150） | `SRR12345678` | ✅ |
| `assembly_accession` | str | `GCF_\d+`（NCBI Assembly，可选） | `GCF_000006945.2` | ⚠️ |
| `bioproject_accession` | str | `PRJNA\d+`（NCBI BioProject，可选） | `PRJNA186481` | ⚠️ |

### 物种分类（4 字段）

| 字段 | 类型 | 格式 | 示例 | 必填 |
|---|---|---|---|---|
| `species` | str | Latin binary | `Salmonella enterica` / `Escherichia coli` | ✅ |
| `serovar` | str | 任意 | `Typhimurium` / `Enteritidis` / `N/A`（E. coli 用） | ✅ |
| `antigenic_formula` | str | Kauffmann-White | `1,4,[5],12:i:1,2` / `N/A` | ⚠️ |
| `ncbi_tax_id` | int | NCBI Taxonomy ID | `28901`（S. enterica） / `562`（E. coli） | ✅ |

### MLST（3 字段，7-gene scheme）

| 字段 | 类型 | 格式 | 示例 | 必填 |
|---|---|---|---|---|
| `mlst_scheme` | str | 固定 | `salmonella` / `E. coli`（# 阴性对照） | ✅ |
| `mlst_st` | int | PubMLST ST 编号 | `19` | ✅ |
| `mlst_alleles` | str | `gene=num;gene=num;...`（7 基因） | `aroC=2;dnaN=7;hemD=12;hisD=9;purE=5;sucA=9;thrA=3` | ✅ |

参考：[PubMLST Salmonella](https://pubmlst.org/organisms/salmonella-spp) 7 个 locus：`aroC, dnaN, hemD, hisD, purE, sucA, thrA`。

### AMR 谱（5 字段）

| 字段 | 类型 | 格式 | 示例 | 必填 |
|---|---|---|---|---|
| `amr_phenotype` | str | 表型卡片法/MIC，`;` 分隔；pansusceptible 写 `Susceptible` | `AMP-R;CIP-R;TET-R;SXT-R` | ✅ |
| `amr_genes` | str | 基因名，`;` 分隔；pansusceptible 留空 | `blaTEM-1;qnrS1;tet(A);sul1;dfrA1` | ✅ |
| `amr_classes` | str | 耐药类别，`;` 分隔 | `β-lactam;Quinolone;Tetracycline;Sulfonamide` | ⚠️ |
| `amr_evidence_sources` | str | `+` 分隔多源验证 | `AMRFinderPlus+ResFinder+CARD` | ✅ |
| `amr_notes` | str | 特殊标记 | `ESBL producer` / `mcr-1 carrier` / `pESI plasmid` | ⚠️ |

**表型缩写**（参考 [NCBI AMRFinderPlus](https://github.com/ncbi/amr/wiki/Running-AMRFinderPlus)）：
- 抗生素缩写：AMP=Ampicillin, CIP=Ciprofloxacin, TET=Tetracycline, SXT=Trimethoprim-sulfamethoxazole, GEN=Gentamicin, CHL=Chloramphenicol, FFC=Ceftriaxone, NAL=Nalidixic acid, AZI=Azithromycin, COL=Colistin
- `-R` = Resistant, `-I` = Intermediate, `-S` = Susceptible

### 毒力与质粒（3 字段）

| 字段 | 类型 | 格式 | 示例 | 必填 |
|---|---|---|---|---|
| `virulence_genes` | str | `;` 分隔 | `spiA;sseL;avrA;invA;sopA` | ⚠️ |
| `plasmid_replicons` | str | `;` 分隔；无写 `none` | `IncF;IncI1;ColRNAI` | ⚠️ |
| `virulence_notes` | str | 特殊标记 | `pESI plasmid (IncX)` / `STEC: stx2a+eae` | ⚠️ |

参考：[VFDB](https://www.mgc.ac.cn/VFs/) / [Victors](http://www.phidias.us/victors/)。

### 元数据（7 字段）

| 字段 | 类型 | 格式 | 示例 | 必填 |
|---|---|---|---|---|
| `source` | str | enum: `food`/`clinical`/`environmental`/`reference`/`animal` | `food` | ✅ |
| `isolation_country` | str | ISO 3166-1 alpha-2 | `US` / `CN` / `GB` | ✅ |
| `isolation_year` | int | 4 位年份 | `2024` | ✅ |
| `isolation_location` | str | 自由文本 | `Beijing` / `FDA-CFSAN` | ⚠️ |
| `sequencing_platform` | str | Illumina 系列 | `Illumina MiSeq` / `Illumina NextSeq 550` | ✅ |
| `read_length` | str | PE 配对 | `PE150` | ✅ |
| `estimated_genome_size_mb` | float | Mb | `4.86` | ✅ |

### 金标准追溯（3 字段）

| 字段 | 类型 | 格式 | 示例 | 必填 |
|---|---|---|---|---|
| `gold_standard_source_url` | str | URL（NCBI PD / EnteroBase / GenomeTrakr） | `https://www.ncbi.nlm.nih.gov/pathogens/...` | ✅ |
| `gold_standard_verified_by` | str | 验证人/工具 | `Hermes-bacmap team` / `cross-validated: EnteroBase+NCBI` | ✅ |
| `gold_standard_verified_date` | date | `YYYY-MM-DD` | `2026-06-27` | ✅ |

### 文件路径（3 字段，FASTQ 下载后填）

| 字段 | 类型 | 格式 | 示例 | 必填 |
|---|---|---|---|---|
| `fastq_r1_path` | str | 本地路径 | `tests/fixtures/.../SAM-TYP-001_R1.fastq.gz` | ⚠️ |
| `fastq_r2_path` | str | 本地路径 | `tests/fixtures/.../SAM-TYP-001_R2.fastq.gz` | ⚠️ |
| `fasta_assembly_path` | str | 本地路径 | `tests/fixtures/.../SAM-TYP-001.fasta` | ⚠️ |

### 备注（1 字段）

| 字段 | 类型 | 格式 | 示例 | 必填 |
|---|---|---|---|---|
| `notes` | str | 自由文本 | `Reference strain LT2; ESBL producer` | ⚠️ |

---

## 双源验证要求（每株的金标准必须满足）

| 字段 | 主源 | 复核源 | 一致性要求 |
|---|---|---|---|
| 血清型 | NCBI Pathogen Detection | EnteroBase in silico | 完全一致 |
| MLST ST | PubMLST | EnteroBase / NCBI | 完全一致 |
| AMR 基因 | AMRFinderPlus (NCBI) | ResFinder (CGE) / CARD | ≥ 95% 一致 |
| 毒力基因 | VFDB | Victors | ≥ 90% 一致 |
| 物种 | NCBI Taxonomy | GTDB | 完全一致 |

---

## 验收标准

| 标准 | 通过条件 |
|---|---|
| 数据完整性 | 11 株全部有 SRA + BioSample + AMR + MLST + 血清型 |
| 双源验证 | 每株金标准答案至少 2 个权威平台一致 |
| FASTQ 下载 | 11 株 FASTQ 已下载到 `data/` 目录 |
| CSV 完整性 | 所有必填字段（✅）填写 |
| JSONL 一致性 | `gold_standard.jsonl` 与 CSV 一致（脚本校验） |

---

## 排除条件（不能用作 Gold standard）

- ❌ 只有 assembly 没有 raw reads 的样本
- ❌ 长读长（ONT/PacBio）样本—— V0.1 只验证 Illumina
- ❌ RNA-seq 或 metagenomic 样本—— V0.1 只验证 isolate WGS
- ❌ SRA reads 数过少（< 1M reads）的样本
- ❌ AMR/MLST 数据缺失或单源未复核的样本
- ❌ 已知有混合污染或低质量（< 30× 覆盖度）的样本
