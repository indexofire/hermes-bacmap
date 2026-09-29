# *Clostridioides difficile*

## Public Health Significance

The leading cause of antibiotic-associated diarrhea. The RT027/BI/NAP1 hypervirulent strain is associated with outbreaks, high relapse rates, and fluoroquinolone resistance.

## Species Identification

| Method | Target | Source |
|---|---|---|
| Marker identification | **tcdA** / **tcdB** (toxin genes, species-specific) | [Kato et al. 2005](https://doi.org/10.1128/JCM.43.12.6108-6112.2005) |

## Toxin Typing (`typing/cdiff_toxin.py`)

| Toxin type | tcdA | tcdB | cdtA/B | Clinical significance |
|---|---|---|---|---|
| Toxigenic strain | + | + | - | Classical toxigenic |
| **RT027 hypervirulent** | + | + | **+** | High virulence, high relapse, escalated infection control |
| Atypical | - | + | - | tcdA-deletion mutant strain |
| Non-toxigenic | - | - | - | No clinical significance |

### References

- Kato H, Yokoyama T, Kato H, Arakawa Y. Detection of toxigenic *Clostridium difficile* in stool by loop-mediated isothermal amplification. *J Clin Microbiol*. 2005;43(12):6108-6112.
- McDonald LC, Killgore GE, Thompson A, et al. An epidemic, toxin gene-variant strain of *Clostridium difficile*. *N Engl J Med*. 2005;353(23):2433-2441. [PMID: 16322603](https://pubmed.ncbi.nlm.nih.gov/16322603/)
- Baktash A, ter Braak EW, Terveer EM, et al. Mechanisms and impact of PCR ribotype 027 epidemic. *Clin Microbiol Infect*. 2021;27(12):1791-1798.

## MLST

| Item | Value |
|---|---|
| Scheme | `cdifficile` (PubMLST) |
| Loci | adk, atpA, dxr, glyA, recA, sodA, tpi |
| ST-11 | RT027 lineage |

## SNP Reference

| Group | Reference genome |
|---|---|
| `cdifficile` | 630 (NC_009089.1, RT012) |
