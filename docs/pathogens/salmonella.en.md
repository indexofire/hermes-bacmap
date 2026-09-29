# Salmonella enterica

## Species Identification

- **Species**: *Salmonella enterica*
- **Target gene**: `invA` (M90846.1, 2176 bp)
- **Database**: `data/reference/species/markers.fasta`
- **Routing rule**: invA positive → Salmonella pipeline

## Serotyping

**SISTR** (`sistr_cmd`) is used to predict serovar, serogroup, and O/H antigen formula.

| Serogroup | Representative serovars | Clinical/epidemiological significance |
|---|---|---|
| B | Typhimurium, 1,4,[5],12:i:- | Most common foodborne serovar; ST34 monophasic is an emerging MDR clone |
| D | Enteritidis, Typhi | Enteritidis is poultry-associated; Typhi causes typhoid fever |
| C1 | Infantis | Poultry-associated, often carries pESI-like plasmids |
| C2-C3 | Newport | MDR potential |
| O:4 | Heidelberg | Associated with poultry meat |

## MLST

- **Tool**: `gmlst` (Python 3.12 `pixi (gmlst now included)`)
- **Scheme**: `salmonella_2` (PubMLST)
- **Loci**: `aroC`, `dnaN`, `hemD`, `hisD`, `purE`, `sucA`, `thrA`

| Common ST | Representative serovars |
|---|---|
| ST11 | Enteritidis |
| ST19 / ST34 | Typhimurium / monophasic Typhimurium |
| ST1 / ST2 | Typhi |
| ST32 | Infantis |
| ST45 / ST118 | Newport |

## AMR Genes

Screening databases: CARD, VFDB, PlasmidFinder.

| Gene | Resistance phenotype |
|---|---|
| `blaCTX-M-15` | ESBL |
| `blaCMY-2` | AmpC |
| `aac(6')-Iy` | Aminoglycosides |
| `qnrS/B` | Low-level fluoroquinolone resistance |
| `sul1/sul2`, `tet(A)` | Sulfonamides, tetracyclines |

## SNP / Phylogeny

- **Reference genome**: NC_003197.2 (*S. enterica* LT2, 4,857,450 bp)
- **Pipeline**: `bwa mem` → `bcftools mpileup/call` → whole-genome SNP matrix → `IQ-TREE`

| Comparison scenario | SNP distance threshold |
|---|---|
| Same outbreak, same serovar | 0–5 SNPs |
| Same serovar, different lineages | 50–200 SNPs |
| Different serovars | 500–3000 SNPs |

## Genome Annotation

- **Engine**: `pyrodigal` CDS prediction + `blastp` vs Prokka DBs
- **Expected**: ~4500–4800 CDS, annotation rate ≈ 75%
