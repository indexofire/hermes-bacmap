# Vibrio parahaemolyticus — Pathogen-Specific Pipeline Details

## Species Identification

| Target gene | Source | Purpose |
|---|---|---|
| toxR (BA000031.2) | species_markers.fasta | Species-specific transcription regulator |
| tlh (M36437.1) | species_markers.fasta | Thermolabile hemolysin (species marker) |

**Routing**: toxR OR tlh positive → V. parahaemolyticus pipeline

## Serotyping

- **Status**: Not yet implemented (自行开发中，不采用 Kaptive)
- **Target**: O/K serotype prediction from genome assemblies
- **Reference approach**: Custom tool under development

## Virulence Detection

- **Database**: `data/reference/vpara_targets.fasta` (toxR + tlh)
- **Hemolysin genes** (separate DBs):
  - tdh (D90238.1) — thermostable direct hemolysin (Kanagawa phenomenon)
  - trh (AY586619.1) — TDH-related hemolysin
  - tlh — thermolabile hemolysin (ubiquitous in V. para, species marker not virulence)
- **Clinical significance**:
  - tdh+ / trh+ → highly pathogenic (pandemic clone RIMD 2210633)
  - tdh+ / trh- → Kanagawa phenomenon positive, gastroenteritis
  - tdh- / trh+ → gastroenteritis (lower incidence)
  - tdh- / trh- → environmental strain, typically non-pathogenic

## MLST

- **Scheme**: PubMLST Vibrio parahaemolyticus
- **Tool**: gmlst (same tool, different scheme)
- **7 loci**: dnaE, gyrB, recA, dtdS, pntA, pyrC, tnaA

## AMR

- Same abricate databases (CARD, VFDB, PlasmidFinder)
- V. para is typically susceptible to most antibiotics; AMR genes uncommon in clinical isolates

## SNP / Phylogenetics

- Not currently implemented
- Reference genome: RIMD 2210633 (NC_004603.1) would be needed
- Typical thresholds: 10-20 SNPs for outbreak (more diverse than Salmonella)

## Current Pipeline Coverage

| Capability | Status |
|---|---|
| Species ID (toxR + tlh) | ✅ Implemented |
| Virulence (tdh/trh/tlh) | ✅ Implemented |
| MLST | ✅ gmlst integration |
| AMR/Virulence DB scan | ✅ abricate |
| Serotype (O/K) | 🔨 自行开发中 |
| SNP phylogenetics | ❌ Not implemented |
