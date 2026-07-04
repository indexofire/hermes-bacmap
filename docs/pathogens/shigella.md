# Shigella / EIEC

## 物种鉴定

- **Species**: *Shigella* / EIEC（肠侵袭性 *E. coli*）
- **Target gene**: `ipaH` (NC_004337.2, 1827 bp)
- **Location**: pINV 侵袭质粒
- **Routing rule**: ipaH 阳性 → Shigella pipeline

## 血清型鉴定 Serotyping

- **Tool**: `shigella_serotyper`
- **Database**: `data/reference/shigella_ref.fasta` (95 seqs)
- **Method**: ported from ShigATyper (CFSAN)
- **覆盖**: 58 种血清型

| 种/群 | 血清型范围 |
|---|---|
| *S. flexneri* | 1a, 1b, 1c, 1d, 2a, 2b, 3a, 3b, 4a, 4b, 5a, 6, 7a, 7b, Y, Yv |
| *S. sonnei* | I, II |
| *S. dysenteriae* | 1–15 |
| *S. boydii* | 1–20 |

## Shigella vs EIEC 区分

| 特征 | Shigella | EIEC |
|---|---|---|
| 分类 | 独立种名 | 仍属 *E. coli* |
| 生化 | 无动力，不发酵乳糖 | 可迟缓发酵乳糖 |
| 致病 | 痢疾 | 水样/痢疾样腹泻 |
| 共有 | 均携带 pINV 与 `ipaH` | 均携带 pINV 与 `ipaH` |

## MLST / AMR

- **MLST**: Achtman 7-gene scheme（同 DEC）
- **AMR/virulence**: CARD、VFDB、PlasmidFinder 扫描
