# 参考数据库

Hermes-bacmap 在 `data/reference/` 分发 **15 个 FASTA 数据库**（按用途分子目录），覆盖物种鉴定、AMR / 毒力 / 质粒检测、血清型、SNP 参考基因组、基因组注释与 V. parahaemolyticus 血清型。数据库随仓库分发，BLAST / bwa 索引需现场构建。

## 物种鉴定数据库

五基因合并库，一次 BLAST 完成所有物种鉴定（详见 [Snakemake 管线 · 物种路由](../architecture/pipeline.md#物种路由五基因系统)）。

| 文件 | 大小 | 序列数 | 用途 |
|---|---|---|---|
| `species/markers.fasta` | 8.3 KB | 5 | **合并库**（invA + uidA + ipaH + toxR + tlh） |
| `salmonella_invA.fasta` | 2.3 KB | 1 | invA 独立库（M90846.1, 2176 bp） |
| `uidA_ecoli.fasta` | 1.3 KB | 1 | uidA（NC_000913.3, 1190 bp） |
| `ipaH_shigella.fasta` | 1.9 KB | 1 | ipaH（NC_004337.2, 1827 bp） |
| `toxR_vpara.fasta` | 1.3 KB | 1 | toxR（BA000031.2, 643 bp） |
| `tlh_vpara.fasta` | 1.7 KB | 1 | tlh（M36437.1, 1302 bp） |

## AMR / 毒力 / 质粒数据库

通过 Snakemake 的 `amr_abricate_*` 规则调用 abricate 检测。

| 文件 | 大小 | 序列数 | 来源 | 检测内容 |
|---|---|---|---|---|
| `amr/card.fasta` | 6.5 MB | ~5,000 | CARD | AMR 耐药基因 |
| `amr/vfdb.fasta` | 6.3 MB | ~4,000 | VFDB | 毒力因子 |
| `plasmid/plasmidfinder.fasta` | 437 KB | ~400 | PlasmidFinder (CGE) | 质粒复制子 |

`bio_gene_scan` Hermes tool 还支持 `resfinder` / `ncbi` / `megares` / `victors` / `ecoli_vf` 等额外数据库（需用户自备 FASTA 并构建索引）。

## 血清型数据库

| 文件 | 大小 | 序列数 | 用途 |
|---|---|---|---|
| `serotype/ecoh.fasta` | 782 KB | 597 | E. coli O/H 抗原（ecoh_serotyper） |
| `serotype/shigella.fasta` | 122 KB | 95 | Shigella 抗原（shigella_serotyper，移植自 ShigATyper） |

Shigella 库支持 58 种血清型：S. flexneri（1a–7b, Y, Yv）、S. sonnei（I, II）、S. dysenteriae（1–15）、S. boydii（1–20）。

## SNP 参考基因组

| 文件 | 大小 | 内容 |
|---|---|---|
| `genomes/salmonella_LT2.fasta` | 4.7 MB | NC_003197.2（S. enterica LT2 染色体, 4,857,450 bp） |
| `genomes/ecoli_k12.fasta` | 4.5 MB | NC_000913.3（E. coli K-12 MG1655, 4,639,675 bp） |
| `genomes/vpara_rimd.fasta` | 5.0 MB | NC_004603.1 + NC_004605.1（V. parahaemolyticus RIMD 2210633, 5,165,770 bp） |

E.coli + Shigella 共享 K-12 MG1655 参考（两者分类学上为同一物种）。V.para 含 2 条染色体。

下载：

```bash
# E.coli K-12 MG1655
curl -sL "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/005/845/GCF_000005845.2_ASM584v2/GCF_000005845.2_ASM584v2_genomic.fna.gz" \
  -o /tmp/ecoli.fna.gz && zcat /tmp/ecoli.fna.gz > data/reference/genomes/ecoli_k12.fasta

# V.parahaemolyticus RIMD 2210633
curl -sL "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/196/095/GCF_000196095.1_ASM19609v1/GCF_000196095.1_ASM19609v1_genomic.fna.gz" \
  -o /tmp/vpara.fna.gz && zcat /tmp/vpara.fna.gz > data/reference/genomes/vpara_rimd.fasta

# bwa index
bwa index data/reference/genomes/ecoli_k12.fasta
bwa index data/reference/genomes/vpara_rimd.fasta
samtools faidx data/reference/genomes/ecoli_k12.fasta
samtools faidx data/reference/genomes/vpara_rimd.fasta
```

仅包含染色体，排除质粒。用前验证：

```bash
grep -c "^>" data/reference/genomes/salmonella_LT2.fasta
# 应为 1（单染色体）
```

## V. parahaemolyticus 毒力数据库

| 文件 | 大小 | 内容 |
|---|---|---|
| `virulence/tdh.fasta` | 1.2 KB | tdh（D90238.1，耐热直接溶血素） |
| `virulence/trh.fasta` | 1.7 KB | trh（AY586619.1，TDH-related 溶血素） |
| `virulence/vpara_targets.fasta` | 5.7 KB | toxR + tlh 合并库 |

## BLAST 索引状态

`bio_blast` / `bio_gene_scan` / `species_identify` 规则依赖 BLAST 索引（`.nhr` / `.nin` / `.nsq`）。索引需用 `makeblastdb` 现场构建：

```bash
# 核酸库（物种鉴定 + AMR + 血清型 + SNP 参考 + V.para）
makeblastdb -in data/reference/species/markers.fasta \
    -dbtype nucl -out data/reference/species_markers
makeblastdb -in data/reference/amr/card.fasta \
    -dbtype nucl -out data/reference/card
makeblastdb -in data/reference/amr/vfdb.fasta \
    -dbtype nucl -out data/reference/vfdb
makeblastdb -in data/reference/plasmid/plasmidfinder.fasta \
    -dbtype nucl -out data/reference/plasmidfinder
makeblastdb -in data/reference/serotype/ecoh.fasta \
    -dbtype nucl -out data/reference/ecoh
makeblastdb -in data/reference/serotype/shigella.fasta \
    -dbtype nucl -out data/reference/shigella_ref
makeblastdb -in data/reference/genomes/salmonella_LT2.fasta \
    -dbtype nucl -out data/reference/genomes/salmonella_LT2
makeblastdb -in data/reference/virulence/vpara_targets.fasta \
    -dbtype nucl -out data/reference/vpara_targets
```

验证：

```bash
ls data/reference/*.nhr
# 应看到每个库对应的 .nhr / .nin / .nsq 三件套
```

## Prokka DB（注释用）

`bio_annotate` 与 `genome_annotation` 规则用 pyrodigal 预测 CDS，再用 Prokka 蛋白库 blastp 注释。蛋白库索引：

```bash
# 蛋白库（注意 -dbtype prot）
makeblastdb -in data/reference/annotation/prokka_sprot.fasta \
    -dbtype prot -out data/reference/prokka_sprot
```

验证：

```bash
ls data/reference/prokka_sprot.phr
# 应存在（蛋白库后缀 .phr / .pin / .psq）
```

若注释率 <30%（全是 hypothetical protein），通常是此索引缺失，重建即可。详见[故障排查](troubleshooting.md)。

## 数据库版本与证据链

每个 ANALYSIS 对象入库时记录数据库版本到三元证据链：

```
database_versions:
  CARD: 2026-Apr-3
  VFDB: 2026-Apr-3
  PlasmidFinder: 2026-Apr-3
  PubMLST salmonella_2: <version>
```

数据库升级后再入库会创建新版本（`create_new_version`），保留历史版本实现可追溯。详见 [GOM · 三元证据链](../architecture/gom.md#三元证据链)。

## 数据库更新

各数据库的官方更新源：

| 数据库 | 官方站点 | 更新频率 |
|---|---|---|
| CARD | <https://card.mcmaster.ca/download> | 季度 |
| VFDB | <http://www.mgc.ac.cn/VFs/download.htm> | 不定期 |
| PlasmidFinder | <https://cge.food.dtu.dk/services/PlasmidFinder.php> | 不定期 |
| PubMLST salmonella_2 | <https://rest.pubmlst.org/db/pubmlst_salmonella_seqdef/schemes/2> | 持续 |

更新后需：重建 BLAST 索引 → 重跑分析 → 入库新版本。

## 相关

- [工具列表](tools.md) — `bio_blast` / `bio_gene_scan` 依赖这些数据库
- [环境准备](../installation/environment.md) — 数据库下载与索引构建步骤
- [Snakemake 管线](../architecture/pipeline.md) — 各规则对应的数据库
- [故障排查](troubleshooting.md) — 数据库缺失错误处理
