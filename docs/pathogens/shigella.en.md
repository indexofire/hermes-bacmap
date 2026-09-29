# Shigella / EIEC

## Species Identification

- **Species**: *Shigella* / EIEC (enteroinvasive *E. coli*)
- **Target gene**: `ipaH` (NC_004337.2, 1827 bp)
- **Location**: pINV invasion plasmid
- **Routing rule**: ipaH positive → Shigella pipeline

## Serotyping

- **Tool**: `shigella_serotyper`
- **Database**: `data/reference/serotype/shigella.fasta` (95 seqs)
- **Method**: ported from ShigATyper (CFSAN)
- **Coverage**: 58 serotypes

| Species/group | Serotype range |
|---|---|
| *S. flexneri* | 1a, 1b, 1c, 1d, 2a, 2b, 3a, 3b, 4a, 4b, 5a, 6, 7a, 7b, Y, Yv |
| *S. sonnei* | I, II |
| *S. dysenteriae* | 1–15 |
| *S. boydii* | 1–20 |

## Shigella vs EIEC Differentiation

| Feature | Shigella | EIEC |
|---|---|---|
| Taxonomy | Distinct species name | Still *E. coli* |
| Biochemistry | Non-motile, does not ferment lactose | May ferment lactose slowly |
| Disease | Dysentery | Watery/dysenteric diarrhea |
| Shared | Both carry pINV and `ipaH` | Both carry pINV and `ipaH` |

## MLST / AMR

- **MLST**: Achtman 7-gene scheme (same as DEC)
- **AMR/virulence**: CARD, VFDB, PlasmidFinder screening
