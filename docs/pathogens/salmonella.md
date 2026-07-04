# Salmonella enterica

## 物种鉴定

- **Species**: *Salmonella enterica*
- **Target gene**: `invA` (M90846.1, 2176 bp)
- **Database**: `data/reference/species_markers.fasta`
- **Routing rule**: invA 阳性 → Salmonella pipeline

## 血清型鉴定 Serotyping

使用 **SISTR** (`sistr_cmd`) 预测 serovar、serogroup 及 O/H 抗原式。

| Serogroup | 代表血清型 | 临床/流行病学意义 |
|---|---|---|
| B | Typhimurium, 1,4,[5],12:i:- | 最常见食源性血清型，ST34 monophasic 为新兴 MDR 克隆 |
| D | Enteritidis, Typhi | Enteritidis 禽源；Typhi 伤寒 |
| C1 | Infantis | 禽源，常携带 pESI-like 质粒 |
| C2-C3 | Newport | MDR 潜力 |
| O:4 | Heidelberg | 禽肉相关 |

## MLST

- **Tool**: `gmlst` (Python 3.12 `.venv-gmlst`)
- **Scheme**: `salmonella_2` (PubMLST)
- **Loci**: `aroC`, `dnaN`, `hemD`, `hisD`, `purE`, `sucA`, `thrA`

| 常见 ST | 代表血清型 |
|---|---|
| ST11 | Enteritidis |
| ST19 / ST34 | Typhimurium / monophasic Typhimurium |
| ST1 / ST2 | Typhi |
| ST32 | Infantis |
| ST45 / ST118 | Newport |

## AMR 耐药基因

扫描数据库：CARD、VFDB、PlasmidFinder。

| 基因 | 耐药表型 |
|---|---|
| `blaCTX-M-15` | ESBL |
| `blaCMY-2` | AmpC |
| `aac(6')-Iy` | 氨基糖苷类 |
| `qnrS/B` | 氟喹诺酮低水平耐药 |
| `sul1/sul2`, `tet(A)` | 磺胺、四环素 |

## SNP / 系统发育

- **Reference genome**: NC_003197.2 (*S. enterica* LT2, 4,857,450 bp)
- **Pipeline**: `bwa mem` → `bcftools mpileup/call` → whole-genome SNP matrix → `IQ-TREE`

| 比较场景 | SNP 距离阈值 |
|---|---|
| 同一次暴发，同血清型 | 0–5 SNPs |
| 同血清型，不同谱系 | 50–200 SNPs |
| 不同血清型 | 500–3000 SNPs |

## 基因组注释

- **Engine**: `pyrodigal` CDS 预测 + `blastp` vs Prokka DBs
- **Expected**: ~4500–4800 CDS，annotation rate ≈ 75%
