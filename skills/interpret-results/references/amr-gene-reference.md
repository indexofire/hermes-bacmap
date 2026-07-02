# AMR Gene Clinical Significance Reference

## Beta-Lactamase Classification

| Gene | Class | Confers Resistance To | Clinical Priority |
|---|---|---|---|
| blaTEM-1 | Penicillinase | Ampicillin, Amoxicillin | Medium |
| blaSHV-12 | ESBL | Cefotaxime, Ceftriaxone, Ceftazidime | High |
| blaCTX-M-15 | ESBL | Cefotaxime (high-level) | High |
| blaCTX-M-14 | ESBL | Cefotaxime | High |
| blaCMY-2 | AmpC | Cefoxitin, Cefotaxime | High |
| blaDHA, blaACC | AmpC | Cephalosporins | High |
| **blaNDM-1** | **Carbapenemase** | **ALL beta-lactams + carbapenems** | **CRITICAL** |
| **blaKPC** | **Carbapenemase** | **Carbapenems** | **CRITICAL** |
| **blaOXA-48** | **Carbapenemase** | **Carbapenems** | **CRITICAL** |
| **blaVIM, blaIMP** | **Carbapenemase** | **Carbapenems** | **CRITICAL** |

## Reporting Rules

- Any **CRITICAL** gene (carbapenemase) → must flag for immediate human review
- ESBL + AmpC co-production → note in report (complicated treatment)
- mcr-1 to mcr-10 → plasmid-mediated colistin resistance (last-line drug)

## Interpretation Phrases for Reports

| Gene Found | Suggested Report Language |
|---|---|
| blaCTX-M-15 | "ESBL-producing; resistant to 3rd-gen cephalosporins" |
| blaNDM-1 | "Carbapenemase-producing (NDM-1); pan-beta-lactam resistant" |
| mcr-1 | "Plasmid-mediated colistin resistance; limited treatment options" |
| qnrS | "Reduced fluoroquinolone susceptibility" |
| tet(A) | "Tetracycline resistance" |

## Non-Beta-Lactam Resistance Genes

| Gene | Drug Class | Notes |
|---|---|---|
| aac(6')-Ib-cr | Aminoglycoside + FQ | Also reduces ciprofloxacin |
| qnrA/B/S | Fluoroquinolone | Plasmid-mediated |
| armA, rmtB | Aminoglycoside | High-level amikacin resistance |
| cat, cmlA | Phenicol/Chloramphenicol | |
| sul1, sul2 | Sulfonamide | Often linked to integrons |
| dfrA | Trimethoprim | Often on class 1 integrons |
| erm(A/B/C) | Macrolide | 23S rRNA methyltransferase |
| vanA/B | Glycopeptide | Vancomycin resistance (critical if found) |
