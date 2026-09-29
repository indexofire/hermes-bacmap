# Case Study: tlh Cross-Reaction — a Marker Misidentifies V. alginolyticus as V. parahaemolyticus

Validation round: species identification validation round 1 (2026-09) · Dataset: 17 RefSeq reference genomes of NCBI Pathogen-tracked isolates
(ground truth in `tests/fixtures/validation_genomes/manifest.tsv`)

## Symptom

| Method | Verdict for GCF_023650915.1 (NCBI-annotated *Vibrio alginolyticus* E110) |
|---|---|
| marker target gene | ❌ V_parahaemolyticus (cross-reaction) |
| mash_refseq (159 MB library) | ✅ Correctly excluded V.para (all nearest neighbors belong to the alginolyticus complex) |

## Forensics (three independent lines of evidence)

1. **Ground truth is trustworthy**: direct skani comparison of E110 vs the V.para RIMD 2210633 reference → **ANI 87.56%, coverage 35.5%**
   (species boundary 95% — far outside it, E110 cannot be V.para); the top 4 nearest neighbors in the full mash library are all the V. alginolyticus
   complex (diabolicus/chemaguriensis/antiquarius, sim≈0.94), with V.para ranked 5th (sim 0.895).
2. **Mechanism**: the hit is **tlh** (identity **85.2%**, coverage 86%), only 0.2 percentage points above the 85% threshold.
   V. alginolyticus carries a tlh homolog (tlh is not absolutely species-specific); toxR did not hit (<85%).
3. **Methodological conclusion**: cross-reactions genuinely exist at the marker layer; the mash ANI layer distinguishes correctly 100% of the time — the premise of the layered arbitration design holds.

## Improvements Landed

| Improvement | Implementation | Verification |
|---|---|---|
| Confidence tiers | Best hit ≥90% → high; 85–90% → medium + notes recommending an ANI re-check | `TestConfidenceTiers` |
| tlh near-relative guard | Single-gene tlh hit <90% → species verdict suppressed to Unknown (notes carry the re-check advice) | `TestNearRelativeGuard` (regression test for this case) |
| Knowledge base | `skills/interpret-results/references/species-marker-crossreactions.md` (AI-layer interpretation rules and phrasing) | — |

After the improvements, this genome's marker result: species=Unknown / confidence=low / notes carrying an ANI re-check recommendation —
the validation harness rose from 94% to **17/17 (100%)**.

## Lessons

- The specificity of a "species-specific marker" is relative — **homologs from close relatives can slip past a lenient threshold in the 85% borderline zone**;
  whenever a new pathogen is introduced, its marker must be challenged with close-relative negative-control experiments (the P1 plan already includes this).
- Whole-genome methods (ANI/MinHash) and markers are complementary evidence layers, not replacements for one another.
- Validation on real data is indispensable: this bug (and the mash distance column-order bug) could not have been caught by unit tests alone.
