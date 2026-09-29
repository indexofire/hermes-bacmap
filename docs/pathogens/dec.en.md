# Diarrheagenic *E. coli* (DEC)

## Species Identification

- **Species**: *Escherichia coli* / DEC
- **Target gene**: `uidA` (NC_000913.3, 1190 bp)
- **Routing rule**: uidA positive → DEC pipeline

## Serotyping

- **Tool**: `ecoh_serotyper` (Python, 597 sequences DB)
- **Database**: `data/reference/serotype/ecoh.fasta`
- **O antigen markers**: `wzm`, `wzt`, `wzx`, `wzy`
- **H antigen markers**: `fliC`, `flkA`, `fllA`, `flnA`
- **Output**: O type + H type, e.g. O157:H7

## Pathotype

Determined by `call_pathotype.py` from VFDB screening results:

| Pathotype | Key genes | Disease |
|---|---|---|
| STEC/EHEC | `stx1` and/or `stx2` + `eae` | HUS |
| EPEC | `eae` (without `stx`) | Infantile diarrhea |
| EIEC | `ipaH` | Invasive dysentery |
| ETEC | `est` and/or `elt` | Traveler's diarrhea |
| EAEC | `aggR` | Persistent diarrhea |

## Big Six non-O157 STEC

The 6 non-O157 STEC under intensified U.S. FDA/FSIS surveillance:

`O26`, `O45`, `O103`, `O111`, `O121`, `O145`

## MLST

- **Scheme**: Achtman 7-gene
- **Loci**: `adk`, `fumC`, `gyrB`, `icd`, `mdh`, `purA`, `recA`
- **Pandemic clone**: ST131 (ESBL + fluoroquinolone-resistant ExPEC)

## AMR / Virulence

Screening databases are the same as for Salmonella (CARD, VFDB, PlasmidFinder).

| Category | Key markers |
|---|---|
| AMR | `blaCTX-M`, `mcr-1`, `qnr` |
| Virulence | `stx1/stx2`, `eae`, `elt/est`, `aggR` |
