# *Listeria monocytogenes*（单增李斯特菌）

## 公卫意义

食源性病原，高危人群（孕妇、新生儿、老年人、免疫抑制）致死率 20-30%。暴发溯源依赖 cgMLST（Pasteur 体系为国际标准）。

## 物种鉴定

| 方法 | 靶标 | 来源 |
|---|---|---|
| marker 鉴定 | **hly**（李斯特溶血素 O，种特异）+ **prs**（*Listeria* 属） | [Doumith et al. 2004](https://doi.org/10.1128/JCM.42.8.3819-3822.2004) |

## 血清群分型（`typing/lmono_serogroup.py`）

移植自 [LisSero](https://github.com/MDU-PHL/LisSero)（MDU-PHL），基于 Doumith 分子血清群方案：

| 血清群 | lmo1118 | lmo0737 | ORF2110 | ORF2819 | 临床意义 |
|---|---|---|---|---|---|
| **1/2a** | - | + | - | - | 最常见临床血清群 |
| **1/2b** | - | - | - | + | 散发李斯特菌病 |
| **1/2c** | + | - | + | - | 常见于食品，低侵袭性 |
| **4b** | - | - | + | + | **与暴发相关，高致死率** |

### 参考文献

- Doumith M, Buchrieser C, Glaser P, Jacquet C, Martin P. Differentiation of the major *Listeria monocytogenes* serovars by multiplex PCR. *J Clin Microbiol*. 2004;42(8):3819-3822. [PMID: 15297515](https://pubmed.ncbi.nlm.nih.gov/15297515/)
- Ragon M, Wirth T, Hollandt F, et al. A new perspective on *Listeria monocytogenes* evolution. *PLoS Pathog*. 2008;4(9):e1000146.
- Moura A, Criscuolo A, Pouseele H, et al. Whole genome-based population biology and epidemiological surveillance of *Listeria monocytogenes*. *Nat Microbiol*. 2016;2:16185.

## MLST

| 项 | 值 |
|---|---|
| Scheme | `listeria`（PubMLST） |
| Loci | abcZ, bglA, cat, dapE, dat, ldh, lhkA |
| 参考 | [Ragon et al. 2008](https://doi.org/10.1128/JCM.01159-07) |

## cgMLST

| 项 | 值 |
|---|---|
| Scheme | Pasteur Lm cgMLST（1701 loci） |
| 分型命名 | CT (Complex Type) |
| 阈值 | CT 相同 = 同克隆系 |
| 参考 | [Moura et al. 2016](https://doi.org/10.1038/nmicrobiol.2016.185) |

## AMR

- AMRFinderPlus organism: `Listeria_monocytogenes`
- 关键耐药: 天然耐受头孢菌素（非获得性）
- gapit: CARD + VFDB

## SNP 参考

| 组 | 参考基因组 |
|---|---|
| `listeria` | EGD-e (NC_003210.1) |
