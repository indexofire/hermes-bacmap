# SNP Distance Interpretation Thresholds

## General Guidelines

| SNP Distance (same serovar) | Epidemiological Interpretation | Action |
|---|---|---|
| 0-5 | Very likely same outbreak / direct transmission | Alert epidemiologist |
| 6-15 | Possibly related — needs epi evidence | Investigate exposure history |
| 16-50 | Unlikely same point-source | Routine surveillance |
| 50-200 | Same serovar, different lineages | No action |
| >200 | Different lineages within serovar | No action |

## Species-Specific Thresholds

| Species | Outbreak Threshold | Notes |
|---|---|---|
| Salmonella enterica | 5-10 SNPs | Most published thresholds |
| E. coli / Shigella | 0-3 SNPs | Very clonal; tight threshold |
| V. parahaemolyticus | 10-20 SNPs | More diverse; higher threshold |

## Caveats

- **Time frame matters**: 0-5 SNP threshold assumes ~3-6 month window
- **Recombination inflates distances**: filter recombinant regions for highly recombinant species
- **Missing data rate**: if >10%, phylogenetic resolution degrades
- **Reference choice**: different references give different absolute SNP counts
- **Always combine with epidemiological data**: time, place, exposure history

## Reading Phylogenetic Trees

| Element | Meaning |
|---|---|
| Branch length | Genetic distance (substitutions per site) |
| Bootstrap ≥90 | Strong support for the clade |
| Bootstrap 70-90 | Moderate support |
| Bootstrap <70 | Weak support — treat cautiously |
| Short terminal branches | Recently diverged (recent common ancestor) |

## Outbreak Investigation Workflow

1. Identify index case → get sample ID
2. Run SNP pipeline: `python scripts/run_analysis.py --snp`
3. Check pairwise distances to index case
4. Samples within threshold → cluster alert
5. Generate tree: `bio_snp_tree` → load into Microreact/PHYLOViZ
6. Combine with epidemiological metadata (dates, locations, food history)
7. Report: cluster size, SNP range, likely source
