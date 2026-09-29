# *Vibrio cholerae*（霍乱弧菌）

## 公卫意义

甲类传染病。产毒株（ctxA+）引起霍乱，需立即上报疾控中心。非产毒环境株不构成公卫事件。

## 物种鉴定

| 方法 | 靶标 | 来源 |
|---|---|---|
| marker 鉴定 | **ompW**（种特异）+ **ctxA**（产毒判定） | [Nandi et al. 2000](https://doi.org/10.1128/JCM.38.11.4145-4151.2000) |
| ANI 面板 | 精选面板含参考株 N16961 | 本项目精选面板 |
| GTDB-Tk | standard 模式仲裁 | GTDB-Tk v2.7 |

## 毒素分型（`typing/vcholerae_genotype.py`）

| 判定 | 基因组合 | 公卫行动 |
|---|---|---|
| **产毒株** | ompW(+) + ctxA(+) | 甲类传染病，立即上报，隔离治疗 |
| **非产毒株** | ompW(+) + ctxA(-) | 环境株，不报告 |
| 不确定 | ctxA(+) ompW(-) | 混合样本或非典型株，需复核 |

### 参考文献

- Nandi B, et al. Rapid identification of *V. cholerae* (ompW primers).
  *J Clin Microbiol*. 2000;38(11):4145-4151. [PMID: 11060070](https://pubmed.ncbi.nlm.nih.gov/11060070/)
- Keasler SP, Hall RH. Detecting and biotyping *Vibrio cholerae* O1 with API strips. *J Clin Microbiol*. 1993;31(7):1921-1924.
- WHO. Cholera vaccines: WHO position paper. *Wkly Epidemiol Rec*. 2010;85(13):117-128.

## MLST

| 项 | 值 |
|---|---|
| Scheme | `vcholerae`（PubMLST） |
| Loci | adk, gyrB, mdh, metE, pntA, purM, pyrC |
| 参考 | [Kotetishvili et al. 2003](https://doi.org/10.1128/JCM.41.6.2511-2518.2003) |

## AMR

- AMRFinderPlus organism: `Vibrio_cholerae`
- gapit 数据库: CARD + VFDB + NCBI
- 关键耐药基因: blaCTX-M, sul1/sul2, tet(A), dfrA1
- 参考: [WHO AMR surveillance report](https://www.who.int/antimicrobial-resistance/en/)

## SNP 参考

| 组 | 参考基因组 |
|---|---|
| `vcholerae` | N16961（O1 El Tor, NC_002505.1） |
