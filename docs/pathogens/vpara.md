# *Vibrio parahaemolyticus*

## 物种鉴定

- **Species**: *Vibrio parahaemolyticus*
- **Target genes**: `toxR` + `tlh`
- **toxR**: 种特异性转录调控因子（BA000031.2）
- **tlh**: thermolabile hemolysin，物种标记（M36437.1）
- **Routing rule**: toxR 或 tlh 阳性 → V. parahaemolyticus pipeline

## 毒力基因

| 基因 | 功能 | 临床意义 |
|---|---|---|
| `tdh` | thermostable direct hemolysin | Kanagawa phenomenon |
| `trh` | TDH-related hemolysin | 协同增强致病性 |
| `tlh` | species marker |  ubiquitous，不直接致病 |

## 毒力组合临床判读

| tdh | trh | 临床意义 |
|---|---|---|
| + | + | 高致病性，多为 pandemic clone RIMD 2210633 |
| + | - | Kanagawa 阳性，胃肠炎 |
| - | + | 胃肠炎（发生率较低） |
| - | - | 通常为环境株，非致病 |

## 血清型

- **Status**: 自行开发中，不采用 Kaptive
- **Target**: 基于组装基因组预测 O/K 血清型

## MLST

- **Scheme**: PubMLST *V. parahaemolyticus*
- **Loci**: `dnaE`, `gyrB`, `recA`, `dtdS`, `pntA`, `pyrC`, `tnaA`
- **Tool**: `gmlst`

## AMR

- 使用 abricate（CARD / VFDB / PlasmidFinder）
- V. parahaemolyticus 临床株通常对多数抗生素敏感，AMR 基因相对少见
