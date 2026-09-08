---
name: interpret-results
description: >
  Pathogen genome result interpretation: serotype (Kauffmann-White), MLST ST
  clinical significance, AMR gene classification (ESBL/carbapenemase/AmpC),
  SNP distance outbreak thresholds (0-5=transmission chain, 6-15=possible),
  cgMLST trace-back (溯源) allele-distance thresholds per species (Salmonella
  HC5/HC10, E. coli serotype-specific, Shigella SNV-confirm, Vpara UNDETERMINED),
  virulence gene database. Load when user asks "what does ST19 mean", "is
  this resistant", "are these related", "what does 7 allele distance mean",
  "溯源", or any result interpretation question. Trigger words: 解读, interpret,
  意味, resistant, 耐药, 关系, related, ST, serotype, cgMLST, 溯源, trace-back,
  allele distance.
version: 0.1.0
metadata:
  hermes:
    tags: [bioinformatics, salmonella, ecoli, shigella, amr, serotype, mlst, snp, cgmlst, trace-back, public-health]
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

## cgMLST Trace-back Interpretation

cgMLST (core-genome MLST) provides high-resolution typing via allele-by-allele
comparison across ~2,000-3,000 core loci (EnteroBase schemes). The **allele
distance (AD)** between two profiles counts loci with differing alleles
(missing-on-either excluded, per EnteroBase HierCC convention; Zhou 2020).
Thresholds are species- and sometimes lineage-specific — always cite the
source when communicating a verdict. Numeric thresholds live in
`workflows/bacmap/config/config.yaml` under `cgmlst.thresholds`; this skill
quotes them. If the two disagree, config wins.

### Per-Species Outbreak Thresholds

| Species / lineage | Outbreak AD | Related AD | Source |
|-------------------|-------------|------------|--------|
| Salmonella (general) | ≤10 (HC5/HC10) | ≤50 (HC50) | Zhou 2020 Genome Res |
| Salmonella ST11 / ST34 (clonal) | ≤3 | — | Ferrato 2023 Frontiers Microbiol |
| E. coli / DEC (general screen) | ≤5 (HC5) | ≤50 (HC50) | Emerjean 2025 CDC EID |
| Shigella (non-sonnei) | ≤5 (HC5) | ≤50 (HC50) | Hawkey 2021 Nat Commun |
| Shigella sonnei | UNRELIABLE | — | Hawkey 2021; Weill 2022 |
| V. parahaemolyticus | NONE (UNDETERMINED) | HC1090 only | Achtman 2022 bioRxiv |

### E. coli Serotype-Specific Sub-Thresholds

The general HC5 screen (≤5 AD) is a first-pass filter; serotype-specific
thresholds refine the verdict (Emerjean 2025 CDC EID):

| Serotype | Outbreak AD |
|----------|-------------|
| O26:H11 | ≤8 |
| O157:H7 | ≤16 |
| O103:H2 | ≤5 |
| O80:H2 | ≤9 |

### Interpretation Rubric

When presenting a cgMLST projection (verdict + nearest references +
min_allele_dist), phrase the result as follows:

1. **OUTBREAK** (min AD ≤ `outbreak_allele_dist`): "Clusters within the
   outbreak threshold for {species} (≤{N} AD, {citation}), consistent with
   direct transmission or a common point source. Recommend epidemiological
   correlation."
2. **RELATED** (outbreak < min AD ≤ `related_allele_dist`): "Related to the
   reference set but outside the outbreak threshold — same lineage/clone,
   insufficient alone for direct transmission."
3. **UNRELATED** (min AD > `related_allele_dist`): "Genetically distinct from
   the reference set; different lineage within the species."
4. **UNDETERMINED**: Used for V. parahaemolyticus (no published threshold) or
   when <50% of loci are called. State explicitly: "no published cgMLST
   outbreak threshold for this species; local calibration required."

### Caveats and Low-Confidence Flags

- **Shigella sonnei**: HC5/HC10 are unreliable due to extreme clonality
  (Hawkey 2021; Weill 2022). Always append: "confirm cgMLST clustering with
  SNV-based phylogeny for S. sonnei."
- **V. parahaemolyticus**: Only the HC1090 species boundary is published
  (Achtman 2022 bioRxiv); no within-species outbreak threshold exists. Ship
  `verdict=UNDETERMINED` with the caveat "no published cgMLST outbreak
  threshold, local calibration required."
- **Low call rate**: If `n_called / n_total < 0.5`, downgrade confidence and
  flag "low call rate ({pct}%), allele distances may be underestimated."
- **Novel / ambiguous loci**: Novel (`~N`) and ambiguous (`N,M`) alleles are
  excluded from distance — high counts reduce resolution; flag if >5%.
- **Single source of truth**: All thresholds live in
  `workflows/bacmap/config/config.yaml` (`cgmlst.thresholds`); this skill
  quotes them. Config wins on disagreement.

## Interpretation Self-Verification (Layer 3 NLI Reflector)

Before presenting any interpretation to the user, reflect it against the
sample's facts. Call `bio_verify_result` with your draft text:

```
bio_verify_result(sample_id="SAM-XXX", interpretation_text="<your draft>")
```

The Layer 3 NLI Reflector decomposes your text into atomic claims
(species / MLST ST / serotype / AMR / virulence / plasmid genes), compares
each against the pipeline's Source-of-Truth facts, and returns per-claim
verdicts (`entailed` / `contradicted` / `unverifiable`) plus an aggregate
`contradiction_rate` (default review threshold 0.1).

Rules:

1. **needs_human_review=true** → your text disagrees with the facts. Find the
   `contradicted` claims, fix your text, and re-verify. Do NOT hand the user
   an interpretation that failed reflection.
2. **Contradicted claims are usually hallucinations**: a gene the sample does
   not carry, a wrong ST, a wrong serotype. Check `evidence` for the actual
   fact value.
3. **Unverifiable claims** (facts missing) → state the limitation explicitly
   instead of asserting the claim.
4. Contradiction events are audit-logged to the GOM (`nli_reflected` event)
   when review is flagged — human reviewers can trace what the AI said via
   `bio_review_flags` (lists flagged samples with contradiction details) or the
   report's "AI 解读自检" section.
