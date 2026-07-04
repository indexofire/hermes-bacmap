# 参考数据库

Hermes-bacmap 在 `data/reference/` 分发 **13 个 FASTA 数据库**，覆盖物种鉴定、AMR / 毒力 / 质粒检测、血清型、SNP 参考基因组与 V. parahaemolyticus 毒力。大部分随仓库提供，部分 BLAST 索引需现场构建。

## 物种鉴定数据库

五基因合并库，一次 BLAST 完成所有物种鉴定（详见 [Snakemake 管线 · 物种路由](../architecture/pipeline.md#物种路由五基因系统)）。

| 文件 | 大小 | 序列数 | 用途 |
|---|---|---|---|
| `species_markers.fasta` | 8.3 KB | 5 | **合并库**（invA + uidA + ipaH + toxR + tlh） |
| `salmonella_invA.fasta` | 2.3 KB | 1 | invA 独立库（M90846.1, 2176 bp） |
| `uidA_ecoli.fasta` | 1.3 KB | 1 | uidA（NC_000913.3, 1190 bp） |
| `ipaH_shigella.fasta` | 1.9 KB | 1 | ipaH（NC_004337.2, 1827 bp） |
| `toxR_vpara.fasta` | 1.3 KB | 1 | toxR（BA000031.2, 643 bp） |
| `tlh_vpara.fasta` | 1.7 KB | 1 | tlh（M36437.1, 1302 bp） |

## AMR / 毒力 / 质粒数据库

通过 Snakemake 的 `amr_abricate_*` 规则调用 abricate 检测。

| 文件 | 大小 | 序列数 | 来源 | 检测内容 |
|---|---|---|---|---|
| `card_sequences.fasta` | 6.5 MB | ~5,000 | CARD | AMR 耐药基因 |
| `vfdb_sequences.fasta` | 6.3 MB | ~4,000 | VFDB | 毒力因子 |
| `plasmidfinder_sequences.fasta` | 437 KB | ~400 | PlasmidFinder (CGE) | 质粒复制子 |

`bio_gene_scan` Hermes tool 还支持 `resfinder` / `ncbi` / `megares` / `victors` / `ecoli_vf` 等额外数据库（需用户自备 FASTA 并构建索引）。

## 血清型数据库

| 文件 | 大小 | 序列数 | 用途 |
|---|---|---|---|
| `ecoh_sequences.fasta` | 782 KB | 597 | E. coli O/H 抗原（ecoh_serotyper） |
| `shigella_ref.fasta` | 122 KB | 95 | Shigella 抗原（shigella_serotyper，移植自 ShigATyper） |

Shigella 库支持 58 种血清型：S. flexneri（1a–7b, Y, Yv）、S. sonnei（I, II）、S. dysenteriae（1–15）、S. boydii（1–20）。

## SNP 参考基因组

| 文件 | 大小 | 内容 |
|---|---|---|
| `salmonella_LT2_ref.fasta` | 4.7 MB | NC_003197.2（S. enterica LT2 染色体, 4,857,450 bp） |

仅包含染色体，排除质粒。用前验证：

```bash
grep -c "^>" data/reference/salmonella_LT2_ref.fasta
# 应为 1（单染色体）
```

## V. parahaemolyticus 毒力数据库

| 文件 | 大小 | 内容 |
|---|---|---|
| `tdh_vpara.fasta` | 1.2 KB | tdh（D90238.1，耐热直接溶血素） |
| `trh_vpara.fasta` | 1.7 KB | trh（AY586619.1，TDH-related 溶血素） |
| `vpara_targets.fasta` | 5.7 KB | toxR + tlh 合并库 |

## BLAST 索引状态

`bio_blast` / `bio_gene_scan` / `species_identify` 规则依赖 BLAST 索引（`.nhr` / `.nin` / `.nsq`）。索引需用 `makeblastdb` 现场构建：

```bash
# 核酸库（物种鉴定 + AMR + 血清型 + SNP 参考 + V.para）
makeblastdb -in data/reference/species_markers.fasta \
    -dbtype nucl -out data/reference/species_markers
makeblastdb -in data/reference/card_sequences.fasta \
    -dbtype nucl -out data/reference/card
makeblastdb -in data/reference/vfdb_sequences.fasta \
    -dbtype nucl -out data/reference/vfdb
makeblastdb -in data/reference/plasmidfinder_sequences.fasta \
    -dbtype nucl -out data/reference/plasmidfinder
makeblastdb -in data/reference/ecoh_sequences.fasta \
    -dbtype nucl -out data/reference/ecoh
makeblastdb -in data/reference/shigella_ref.fasta \
    -dbtype nucl -out data/reference/shigella_ref
makeblastdb -in data/reference/salmonella_LT2_ref.fasta \
    -dbtype nucl -out data/reference/salmonella_LT2_ref
makeblastdb -in data/reference/vpara_targets.fasta \
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
makeblastdb -in data/reference/prokka_sprot_abricate.fasta \
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
