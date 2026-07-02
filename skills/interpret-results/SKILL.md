---
name: interpret-results
description: >
  Pathogen genome result interpretation: serotype (Kauffmann-White), MLST ST
  clinical significance, AMR gene classification (ESBL/carbapenemase/AmpC),
  SNP distance outbreak thresholds (0-5=transmission chain, 6-15=possible),
  virulence gene database. Load when user asks "what does ST19 mean", "is
  this resistant", "are these related", or any result interpretation question.
  Trigger words: 解读, interpret, 意味, resistant, 耐药, 关系, related, ST, serotype.
version: 0.1.0
metadata:
  hermes:
    tags: [bioinformatics, salmonella, ecoli, shigella, amr, serotype, mlst, snp, public-health]
    category: bioinfo
---

# Pathogen Genome Result Interpretation Guide

## When to Use

Load this skill when the user asks about interpreting analysis results:
- "What does serotype Typhimurium mean?"
- "Is ST19 dangerous?"
- "What does blaCTX-M-15 resistance mean?"
- "Are these two samples related?" (SNP distance interpretation)
- "What serogroup is this?"

## Salmonella Serotype Interpretation

### Antigenic Formula Format

Salmonella serotype names follow the Kauffmann-White scheme:
`O抗原 : H1 (phase 1) : H2 (phase 2)`

Example: Typhimurium = `1,4,[5],12 : i : 1,2`
- `1,4,[5],12` = somatic O antigens (O:4 group = serogroup B)
- `[5]` = optional antigen (may or may not be present)
- `i` = phase 1 flagellar antigen
- `1,2` = phase 2 flagellar antigen

### Clinically Important Serotypes

| Serovar | Serogroup | Typical ST | Clinical Significance |
|---------|-----------|------------|----------------------|
| Typhimurium | B (O:4) | ST19, ST34 | Broad-host-range; common in foodborne outbreaks; MDR common |
| Enteritidis | D1 (O:9) | ST11 | Egg-associated; most common nontyphoidal globally |
| Typhi | A (O:1) | ST1, ST2 | Typhoid fever (human-restricted); treat with fluoroquinolones |
| Infantis | C1 (O:7) | ST32 | Emerging MDR clones worldwide |
| Newport | C2 (O:8) | ST45, ST118 | MDR-AmpC phenotype (AmpC + CMY-2) |
| Thompson | C1 (O:7) | ST26 | Occasional outbreaks; usually susceptible |

### Monophasic Typhimurium

`1,4,[5],12:i:-` (missing phase 2 flagellin) is a globally emerging MDR variant.
ST34 is the dominant monophasic clone.

## E. coli / DEC Serotype Interpretation

### Pathotype Classification

| Pathotype | Key Genes | Disease |
|-----------|-----------|---------|
| STEC/EHEC | stx1 and/or stx2 + eae | Hemolytic uremic syndrome (HUS) |
| EPEC | eae (without stx) | Pediatric diarrhea |
| EIEC/Shigella | ipaH | Invasive dysentery |
| ETEC | est (ST) and/or elt (LT) | Traveler's diarrhea |
| EAEC | aggR | Persistent diarrhea |

### Important STEC Serotypes

O157:H7 is the most notorious, but "Big Six" non-O157 STEC are also regulated:
O26, O45, O103, O111, O121, O145

### Shigella vs EIEC

Shigella and EIEC are genetically E. coli but classified separately:
- Shigella: ipaH positive, biochemically inactive (lysine decarboxylase negative)
- EIEC: ipaH positive, more biochemically active
- Shigella serotypes: S. flexneri (1a-6, Y, Yv), S. sonnei, S. boydii (1-20), S. dysenteriae (1-15)

## MLST Interpretation

### Salmonella (7-gene scheme: aroC-dnaN-hemD-hisD-purE-sucA-thrA)

- ST19 = Typhimurium global epidemic clone
- ST11 = Enteritidis (phage type 4 = classic poultry-associated)
- ST32 = Infantis (South American MDR clone, now global)
- ST34 = Monophasic Typhimurium variant (1,4,[5],12:i:-)

### E. coli (Achtman 7-gene scheme)

- ST10, ST167, ST410, ST648 = Extra-intestinal pathogenic E. coli (ExPEC) complexes
- ST131 = Pandemic fluoroquinolone-resistant + ESBL-producing clone

## AMR Gene Interpretation

### Beta-lactamases

| Gene | Class | Confers Resistance To |
|------|-------|----------------------|
| blaTEM-1 | Penicillinase | Ampicillin, Amoxicillin |
| blaSHV-12 | ESBL | Cefotaxime, Ceftriaxone, Ceftazidime |
| blaCTX-M-15 | ESBL | Cefotaxime (high-level), Ceftriaxone |
| blaCTX-M-14 | ESBL | Cefotaxime (lower MIC than -15) |
| blaCMY-2 | AmpC | Cefoxitin, Cefotaxime (cephalosporinase) |
| blaNDM-1 | Carbapenemase | ALL beta-lactams including carbapenems (last-resort) |
| blaKPC | Carbapenemase | Carbapenems |

### Clinical Significance Tiers

- **Carbapenemases** (blaNDM, blaKPC, blaOXA-48, blaVIM, blaIMP): Critical — last-line resistance
- **ESBL** (blaCTX-M, blaSHV-ESBL, blaPER): Extended-spectrum cephalosporin resistance
- **AmpC** (blaCMY, blaDHA, blaACC): Cephalosporinase; may mask ESBL detection
- **Colistin resistance** (mcr-1 to mcr-10): Plasmid-mediated colistin resistance

### Fluoroquinolone Resistance

- Chromosomal mutations in gyrA/parC (not detected by abricate)
- Plasmid-mediated: qnrA/B/S, aac(6')-Ib-cr, qepA

### Aminoglycoside Resistance

- aac genes (acetyltransferases), aph (phosphotransferases), ant (nucleotidyltransferases)
- Important: aac(6')-Ib-cr also confers reduced fluoroquinolone susceptibility

## SNP Distance Interpretation

### General Guidelines (WGS-based epidemiology)

| SNP Distance | Interpretation (same serovar) |
|-------------|------------------------------|
| 0-5 SNPs | Very likely part of same outbreak / direct transmission chain |
| 6-15 SNPs | Possibly related (needs epidemiological evidence) |
| 16-50 SNPs | Unlikely same point-source outbreak |
| 50-200 SNPs | Same serovar, different lineages |
| >200 SNPs | Different lineages within serovar |

### Caveats

- Thresholds vary by species, recombination rate, and time frame
- Salmonella: typically 5-10 SNP threshold for outbreak detection
- E. coli/Shigella: 0-3 SNPs for direct transmission (clonal species)
- Recombinant regions can inflate distances artificially
- Missing data rate >10% reduces phylogenetic resolution
- Always combine with epidemiological data (time, place, exposure)

### Reading Phylogenetic Trees

- **Branch length** = genetic distance (substitutions per site)
- **Bootstrap values** (>90 = strong support; 70-90 = moderate; <70 = weak)
- **Clade** = a group of samples sharing a common ancestor
- Samples clustering together with short branches are closely related

## Virulence Gene Interpretation (Salmonella)

| Gene | Function | Significance |
|------|----------|-------------|
| spiC/D/E/F | SPI-2 type III secretion | Intracellular survival |
| invA/B/C/D | SPI-1 invasion | Epithelial invasion |
| ssaT/U/V | SPI-2 secretion system | Systemic infection |
| sefA | SEF14 fimbriae | Enteritidis-specific adhesion |
| spvB/C | Virulence plasmid | Systemic virulence (non-typhoidal) |
| bcfC | Fimbrial adhesin | Colonization |
| sopE/E2 | Effector proteins | Inflammation induction |

## Report Generation Guidance

When summarizing results for users:

1. Always start with species confirmation (was the identity confirmed?)
2. Highlight clinically actionable findings (AMR genes, pathotype)
3. Flag unusual or concerning results (carbapenemase, STEC with stx2)
4. Provide context (is this serotype common? is this ST associated with outbreaks?)
5. Note limitations (in silico predictions need phenotypic confirmation)
