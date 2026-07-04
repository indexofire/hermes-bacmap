# DEC / Shigella / EIEC — Pathogen-Specific Pipeline Details

## Species Identification

| Pathogen | Target gene | Source | Routing |
|---|---|---|---|
| E. coli / DEC | uidA (NC_000913.3, 1190 bp) | species_markers.fasta | uidA positive → DEC pipeline |
| Shigella / EIEC | ipaH (NC_004337.2, 1827 bp) | species_markers.fasta | ipaH positive → Shigella pipeline |

**Note**: Shigella is genetically E. coli but classified separately. ipaH is on the invasion plasmid (pINV). EIEC carries the same plasmid but is biochemically more E. coli-like.

## Serotyping

### DEC (E. coli) — ecoh_serotyper

- **Database**: `data/reference/ecoh_sequences.fasta` (597 seqs, 782 KB)
- **O antigen markers**: wzm, wzt, wzx, wzy
- **H antigen markers**: fliC, flkA, fllA, flnA
- **Output**: O type + H type + full serotype (e.g., O157:H7)
- **Big Six non-O157 STEC**: O26, O45, O103, O111, O121, O145

### Shigella — shigella_serotyper

- **Database**: `data/reference/shigella_ref.fasta` (95 seqs, 122 KB)
- **Method**: Ported from ShigATyper (CFSAN)
- **Supported species/serotypes** (58 total):
  - S. flexneri: 1a, 1b, 1c, 1d, 2a, 2b, 3a, 3b, 4a, 4b, 5a, 6, 7a, 7b, Y, Yv
  - S. sonnei: I, II
  - S. dysenteriae: 1-15
  - S. boydii: 1-20

### Serotype Routing Logic (collect_summary.py)

```python
if "Shigella" in species and serotype != "Undetermined":
    primary = shigella_serotype       # shigella_serotyper
elif ecoh_serotype != "-:-":
    primary = ecoh_serotype           # ecoh_serotyper (DEC/EIEC)
else:
    primary = sistr_serovar           # SISTR (fallback for Salmonella)
```

## DEC Pathotype Classification

Determined by `call_pathotype.py` from VFDB gene scan results:

| Pathotype | Key Genes | Disease |
|---|---|---|
| STEC/EHEC | stx1 and/or stx2 + eae | Hemolytic uremic syndrome (HUS) |
| EPEC | eae (without stx) | Pediatric diarrhea |
| EIEC/Shigella | ipaH | Invasive dysentery |
| ETEC | est (ST) and/or elt (LT) | Traveler's diarrhea |
| EAEC | aggR | Persistent diarrhea |

## MLST

- **Scheme**: E. coli uses Achtman 7-gene scheme (adk, fumC, gyrB, icd, mdh, purA, recA)
- **Tool**: gmlst (same as Salmonella, different scheme)
- **Important STs**: ST131 (pandemic ESBL/fluoroquinolone-resistant ExPEC)

## AMR / Virulence

- Same databases as Salmonella (CARD, VFDB, PlasmidFinder)
- **Key AMR in DEC/Shigella**: blaCTX-M (ESBL), mcr-1 (colistin), qnr (fluoroquinolone)
- **Key virulence**: stx1/stx2 (Shiga toxin), eae (intimin), ipaH (invasion), elt/est (enterotoxin)

## SNP / Phylogenetics

- Not currently implemented for DEC/Shigella (different reference genomes needed)
- E. coli/Shigella are highly clonal: SNP thresholds are tighter (0-3 SNPs for direct transmission)
