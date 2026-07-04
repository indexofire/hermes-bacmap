# Diarrheagenic *E. coli* (DEC)

## 物种鉴定

- **Species**: *Escherichia coli* / DEC
- **Target gene**: `uidA` (NC_000913.3, 1190 bp)
- **Routing rule**: uidA 阳性 → DEC pipeline

## 血清型鉴定 Serotyping

- **Tool**: `ecoh_serotyper` (Python, 597 sequences DB)
- **Database**: `data/reference/ecoh_sequences.fasta`
- **O antigen markers**: `wzm`, `wzt`, `wzx`, `wzy`
- **H antigen markers**: `fliC`, `flkA`, `fllA`, `flnA`
- **Output**: O 型 + H 型，例如 O157:H7

## 致病型 Pathotype

由 `call_pathotype.py` 基于 VFDB 扫描结果判定：

| Pathotype | 关键基因 | 疾病 |
|---|---|---|
| STEC/EHEC | `stx1` 和/或 `stx2` + `eae` | HUS |
| EPEC | `eae`（无 `stx`） | 婴幼儿腹泻 |
| EIEC | `ipaH` | 侵袭性痢疾 |
| ETEC | `est` 和/或 `elt` | 旅行者腹泻 |
| EAEC | `aggR` | 持续性腹泻 |

## Big Six non-O157 STEC

美国 FDA/FSIS 重点监测的 6 种非 O157 STEC：

`O26`, `O45`, `O103`, `O111`, `O121`, `O145`

## MLST

- **Scheme**: Achtman 7-gene
- **Loci**: `adk`, `fumC`, `gyrB`, `icd`, `mdh`, `purA`, `recA`
- **Pandemic clone**: ST131（ESBL + 氟喹诺酮耐药 ExPEC）

## AMR / 毒力

扫描数据库同 Salmonella（CARD、VFDB、PlasmidFinder）。

| 类别 | 关键标记 |
|---|---|
| AMR | `blaCTX-M`, `mcr-1`, `qnr` |
| 毒力 | `stx1/stx2`, `eae`, `elt/est`, `aggR` |
