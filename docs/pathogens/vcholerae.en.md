# *Vibrio cholerae*

## Public Health Significance

Class A notifiable disease. Toxigenic strains (ctxA+) cause cholera and must be reported to the CDC immediately. Non-toxigenic environmental strains do not constitute a public health event.

## Species Identification

| Method | Target | Source |
|---|---|---|
| Marker identification | **ompW** (species-specific) + **ctxA** (toxigenicity determination) | [Nandi et al. 2000](https://doi.org/10.1128/JCM.38.11.4145-4151.2000) |
| ANI panel | Curated panel including reference strain N16961 | Curated panel from this project |
| GTDB-Tk | Arbitration in standard mode | GTDB-Tk v2.7 |

## Toxigenicity Typing (`typing/vcholerae_genotype.py`)

| Call | Gene combination | Public health action |
|---|---|---|
| **Toxigenic strain** | ompW(+) + ctxA(+) | Class A notifiable disease; report immediately, isolate and treat |
| **Non-toxigenic strain** | ompW(+) + ctxA(-) | Environmental strain, not reportable |
| Uncertain | ctxA(+) ompW(-) | Mixed sample or atypical strain; review required |

### References

- Nandi B, et al. Rapid identification of *V. cholerae* (ompW primers).
  *J Clin Microbiol*. 2000;38(11):4145-4151. [PMID: 11060070](https://pubmed.ncbi.nlm.nih.gov/11060070/)
- Keasler SP, Hall RH. Detecting and biotyping *Vibrio cholerae* O1 with API strips. *J Clin Microbiol*. 1993;31(7):1921-1924.
- WHO. Cholera vaccines: WHO position paper. *Wkly Epidemiol Rec*. 2010;85(13):117-128.

## MLST

| Item | Value |
|---|---|
| Scheme | `vcholerae` (PubMLST) |
| Loci | adk, gyrB, mdh, metE, pntA, purM, pyrC |
| Reference | [Kotetishvili et al. 2003](https://doi.org/10.1128/JCM.41.6.2511-2518.2003) |

## AMR

- AMRFinderPlus organism: `Vibrio_cholerae`
- gapit databases: CARD + VFDB + NCBI
- Key AMR genes: blaCTX-M, sul1/sul2, tet(A), dfrA1
- Reference: [WHO AMR surveillance report](https://www.who.int/antimicrobial-resistance/en/)

## SNP Reference

| Group | Reference genome |
|---|---|
| `vcholerae` | N16961 (O1 El Tor, NC_002505.1) |
