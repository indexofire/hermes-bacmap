# Salmonella enterica — Pathogen-Specific Pipeline Details

## Species Identification

- **Target gene**: invA (M90846.1, 2176 bp)
- **Database**: `data/reference/species_markers.fasta` (merged 5-gene DB)
- **Routing**: invA positive → Salmonella pipeline

## Serotyping

- **Tool**: SISTR (sistr_cmd via pixi)
- **Output**: serovar + serogroup + O/H antigen formula
- **Key serovars**: Typhimurium (ST19/ST34), Enteritidis (ST11), Typhi (ST1/ST2), Infantis (ST32), Newport (ST45/ST118)
- **Monophasic Typhimurium**: `1,4,[5],12:i:-` (ST34, emerging MDR variant)

## MLST

- **Scheme**: salmonella_2 (PubMLST)
- **Tool**: gmlst (Python 3.12 in `.venv-gmlst`)
- **7 loci**: aroC, dnaN, hemD, hisD, purE, sucA, thrA

## SNP / Phylogenetics

- **Reference genome**: NC_003197.2 (S. enterica LT2 chromosome, 4,857,450 bp)
- **Pipeline**: bwa mem → joint bcftools mpileup+call → whole-genome SNP matrix → IQ-TREE (GTR, UFBoot 1000)
- **Typical SNP distances**:
  - Same serovar, same outbreak: 0-5 SNPs
  - Same serovar, different lineages: 50-200 SNPs
  - Different serovars: 500-3000 SNPs

## AMR / Virulence

- **Databases**: abricate CARD (AMR), VFDB (virulence), PlasmidFinder (plasmid)
- **Common AMR genes in Salmonella**:
  - blaCTX-M-15 (ESBL), blaCMY-2 (AmpC),aac(6')-Iy (aminoglycoside)
  - qnrS/B (fluoroquinolone), sul1/sul2 (sulfonamide), tet(A) (tetracycline)
- **Key virulence**: SPI-1 (invA invasin), SPI-2 (intracellular survival), spvB/C (systemic virulence)

## Genome Annotation

- **Engine**: pyrodigal (CDS prediction) + blastp vs Prokka DBs (sprot/IS/AMR)
- **Expected**: ~4500-4800 CDS, 70-80% annotation rate for S. enterica
