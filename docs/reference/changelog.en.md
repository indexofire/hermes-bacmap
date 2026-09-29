# Changelog

For the complete change history, see [CHANGELOG.md](https://github.com/indexofire/hermes-bacmap/blob/main/CHANGELOG.md) in the project root.

## Version Overview

| Version | Theme | Key updates |
|---|---|---|
| **V0.1** | Salmonella MVP | `invA` species identification, SISTR serotyping, gmlst MLST, abricate AMR/virulence/plasmid scanning |
| **V0.2** | DEC + Shigella expansion | `uidA` / `ipaH` dual target genes, `ecoh_serotyper`, ShigATyper port with 58 serotypes, pathotype determination |
| **V0.3** | SNP + phylogenetics | Salmonella LT2 reference genome, `bwa` + `bcftools` + `IQ-TREE` whole-genome SNP tree, outbreak thresholds |
| **V0.4** | Species unification and architecture slimming | `species_identifier.py` merges 4 rules into 1 BLAST run, `gene_scanner` generic engine, serotype routing logic |
| **V0.5** | Engine + annotation + Web UI + LLM | Native genome annotation (`pyrodigal` + Prokka DBs), HTML reports, Hermes 24 tools, LLM auto-interpretation |

## Highlights per Version

### V0.1 Salmonella MVP

- Established the `invA`-based species identification framework
- Integrated SISTR serotype prediction and gmlst `salmonella_2` MLST
- Scanned CARD, VFDB, and PlasmidFinder with abricate

### V0.2 DEC + Shigella

- Added the `uidA` (E. coli/DEC) and `ipaH` (Shigella/EIEC) target genes
- Completed the three-gene cross-validation matrix (no cross-reactions)
- Added `call_pathotype.py` to determine STEC/EPEC/EIEC/ETEC/EAEC

### V0.3 SNP Phylogenetics

- Introduced the NC_003197.2 LT2 reference genome
- Built the joint VCF → SNP matrix → IQ-TREE workflow
- Defined the 0–5 SNPs same-outbreak threshold

### V0.4 Architecture Slimming

- `species/markers.fasta` unified species identification
- `gene_scanner` replaced duplicated BLAST logic
- `collect_summary.py` auto-selects the primary serotype

### V0.5 Intelligence Upgrade

- `genome_annotator.py` native annotation, expecting ~4500 CDS and a 75% annotation rate
- HTML reports integrate the verifier evidence chain
- 24 Hermes tools support natural-language interaction

## Current Status

- Supports 4 foodborne pathogens: Salmonella, DEC, Shigella/EIEC, V. parahaemolyticus
- End-to-end Snakemake pipeline + GOM ingestion + HTML reports
- Fully validated on all 10 gold standard isolates

> For full details, PR links, and unreleased changes, see [CHANGELOG.md](https://github.com/indexofire/hermes-bacmap/blob/main/CHANGELOG.md).
