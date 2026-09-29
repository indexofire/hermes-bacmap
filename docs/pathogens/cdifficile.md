# *Clostridioides difficile*（艰难梭菌）

## 公卫意义

抗生素相关腹泻的首要病原。RT027/BI/NAP1 高产毒株与暴发、高复发率、氟喹诺酮耐药相关。

## 物种鉴定

| 方法 | 靶标 | 来源 |
|---|---|---|
| marker 鉴定 | **tcdA** / **tcdB**（毒素基因，种特异） | [Kato et al. 2005](https://doi.org/10.1128/JCM.43.12.6108-6112.2005) |

## 毒素分型（`typing/cdiff_toxin.py`）

| 毒素型 | tcdA | tcdB | cdtA/B | 临床意义 |
|---|---|---|---|---|
| 产毒株 | + | + | - | 经典产毒 |
| **RT027 高产毒** | + | + | **+** | 高毒力、高复发、感控升级 |
| 非典型 | - | + | - | tcdA 缺失突变株 |
| 非产毒 | - | - | - | 无临床意义 |

### 参考文献

- Kato H, Yokoyama T, Kato H, Arakawa Y. Detection of toxigenic *Clostridium difficile* in stool by loop-mediated isothermal amplification. *J Clin Microbiol*. 2005;43(12):6108-6112.
- McDonald LC, Killgore GE, Thompson A, et al. An epidemic, toxin gene-variant strain of *Clostridium difficile*. *N Engl J Med*. 2005;353(23):2433-2441. [PMID: 16322603](https://pubmed.ncbi.nlm.nih.gov/16322603/)
- Baktash A, ter Braak EW, Terveer EM, et al. Mechanisms and impact of PCR ribotype 027 epidemic. *Clin Microbiol Infect*. 2021;27(12):1791-1798.

## MLST

| 项 | 值 |
|---|---|
| Scheme | `cdifficile`（PubMLST） |
| Loci | adk, atpA, dxr, glyA, recA, sodA, tpi |
| ST-11 | RT027 谱系 |

## SNP 参考

| 组 | 参考基因组 |
|---|---|
| `cdifficile` | 630 (NC_009089.1, RT012) |
