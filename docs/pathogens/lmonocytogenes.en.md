# *Listeria monocytogenes*

## Public Health Significance

Foodborne pathogen with 20-30% fatality in high-risk groups (pregnant women, neonates, the elderly, immunocompromised). Outbreak trace-back relies on cgMLST (Pasteur scheme, the international standard).

## Species Identification

| Method | Target | Source |
|---|---|---|
| Marker identification | **hly** (listeriolysin O, species-specific) + **prs** (*Listeria* genus) | [Doumith et al. 2004](https://doi.org/10.1128/JCM.42.8.3819-3822.2004) |

## Serogroup Typing (`typing/lmono_serogroup.py`)

Ported from [LisSero](https://github.com/MDU-PHL/LisSero) (MDU-PHL), based on the Doumith molecular serogroup scheme:

| Serogroup | lmo1118 | lmo0737 | ORF2110 | ORF2819 | Clinical significance |
|---|---|---|---|---|---|
| **1/2a** | - | + | - | - | Most common clinical serogroup |
| **1/2b** | - | - | - | + | Sporadic listeriosis |
| **1/2c** | + | - | + | - | Common in foods, low invasiveness |
| **4b** | - | - | + | + | **Outbreak-associated, high fatality rate** |

### References

- Doumith M, Buchrieser C, Glaser P, Jacquet C, Martin P. Differentiation of the major *Listeria monocytogenes* serovars by multiplex PCR. *J Clin Microbiol*. 2004;42(8):3819-3822. [PMID: 15297515](https://pubmed.ncbi.nlm.nih.gov/15297515/)
- Ragon M, Wirth T, Hollandt F, et al. A new perspective on *Listeria monocytogenes* evolution. *PLoS Pathog*. 2008;4(9):e1000146.
- Moura A, Criscuolo A, Pouseele H, et al. Whole genome-based population biology and epidemiological surveillance of *Listeria monocytogenes*. *Nat Microbiol*. 2016;2:16185.

## MLST

| Item | Value |
|---|---|
| Scheme | `listeria` (PubMLST) |
| Loci | abcZ, bglA, cat, dapE, dat, ldh, lhkA |
| Reference | [Ragon et al. 2008](https://doi.org/10.1128/JCM.01159-07) |

## cgMLST

| Item | Value |
|---|---|
| Scheme | Pasteur Lm cgMLST (1701 loci) |
| Type nomenclature | CT (Complex Type) |
| Threshold | Identical CT = same clonal lineage |
| Reference | [Moura et al. 2016](https://doi.org/10.1038/nmicrobiol.2016.185) |

## AMR

- AMRFinderPlus organism: `Listeria_monocytogenes`
- Key resistance: intrinsic cephalosporin tolerance (not acquired)
- gapit: CARD + VFDB

## SNP Reference

| Group | Reference genome |
|---|---|
| `listeria` | EGD-e (NC_003210.1) |
