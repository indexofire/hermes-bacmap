# Tiered Species Identification System

Hermes-bacmap adopts a **tiered identification** architecture: multiple methods coexist, with unified switching and
cross-method arbitration. Species identification answers "**what species is it**", complementing — not duplicating —
the typing modules (virulence/serotype/resistance, which answer "**how dangerous is it**").

## Architecture Overview

```
User / AI conversation
    ↓
species_mode unified switching (config.yaml / CLI / conversation tool)
    ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Tiered identification methods               │
│                                                                 │
│  Layer 1 · marker genes (multigene_identifier.py)               │
│  ├─ 80 marker genes / 38 decision rules / 34 pathogens          │
│  ├─ seconds / 0 extra databases / species_mode=simple           │
│  └─ Use: rapid first-pass screening, routine surveillance       │
│                                                                 │
│  Layer 2 · ANI whole-genome alignment                           │
│  ├─ skani panel (284 strains / 125 MB)   → species_mode=panel   │
│  ├─ Mash RefSeq sketch (159 MB)          → species_mode=mash_refseq │
│  ├─ skani GTDB full DB (30 GB)           → species_mode=skani_gtdb │
│  └─ Use: confirmation, close-species discrimination             │
│                                                                 │
│  Layer 3 · mixed-sample decomposition                           │
│  ├─ sourmash gather (3.7 GB)             → species_mode=sourmash│
│  └─ Unique: minimal set-cover decomposition, mixture detection  │
│                                                                 │
│  Layer 4 · gold-standard arbitration                            │
│  ├─ GTDB-Tk + CheckM2 (98GB + 140GB RAM) → species_mode=standard│
│  └─ Use: dispute arbitration, regulatory review, novel species  │
│                                                                 │
│  Layer 0 · reads-level pre-screen (independent switch)          │
│  ├─ Kraken2 custom DB                  → kraken2_prefilter=true │
│  └─ Earliest contamination/mixture alert + human read removal   │
└─────────────────────────────────────────────────────────────────┘
    ↓
species_consensus (cross-method arbitration)
    ↓
Deterministic Verifier (Layer 2 defense)
    ↓
GOM ANALYSIS objects (immutable, multiple methods coexist)
    ↓
bio_species_compare tool (consistency matrix + arbitration verdict + NEEDS_REVIEW)
    ↓
LLM interpretation (skill-guided, only the "what it means" reading)
```

## Tiered Methods in Detail

### Layer 1: marker gene identification (`multigene_identifier.py`)

| Item | Value |
|---|---|
| Database | `markers_v2` BLAST DB (80 sequences / 108,808 bp) |
| Decision rules | `marker_rules.yaml` (38 rules, covering 34 pathogens) |
| Runtime | Seconds per strain |
| Extra storage | 0 |
| Switch | `species_mode=simple` (default) |

#### Multi-gene combination decision principle

Single-gene identification has known limitations (cross-reaction, intra-species homology); this project uses **multi-gene combinations** to improve accuracy:

| Discrimination challenge | Single-gene flaw | Combination rule | Source |
|---|---|---|---|
| E. coli vs Shigella | uidA positive in 44% of Shigella | uidA + lacY + gadA ≥2 hits → DEC; ipaH(+)+lacY(-) → Shigella | [FDA BAM Ch.4](https://www.fda.gov/media/183681/download) |
| V. para vs V. alginolyticus | tlh cross-reaction (85.2%) | toxR ≥90% + tlh ≥90% → V.para; tlh alone <90% suppresses the call | Validated in this project |
| C. jejuni vs C. coli | Single-gene false negatives | mapA(+) → jejuni; ceuE(+) → coli | [Linton et al. 1997](https://doi.org/10.1128/jcm.35.11.2568-2572.1997) |
| L. mono vs L. innocua | Phenotypically indistinguishable | prs(+) + hly(+) → L. mono; prs(+) hly(-) → non-pathogenic | [Doumith et al. 2004](https://doi.org/10.1128/JCM.42.8.3819-3822.2004) |
| B. anthracis vs B. cereus | 16S cannot discriminate | pagA + capB double positive → B. anthracis | [CDC](https://www.cdc.gov/anthrax/) |
| Toxigenic vs non-toxigenic V. cholerae | Species ID does not flag toxicity | ompW(+) + ctxA(+) → toxigenic strain (Class A) | [Nandi et al. 2000](https://doi.org/10.1128/JCM.38.11.4145-4151.2000) |

#### Known cross-reaction guards

| Gene | Cross-reacting species | Cross rate | Guard mechanism |
|---|---|---|---|
| tlh | V. alginolyticus | ~85% identity | Close-relative guard: alone <90% makes no call |
| uidA | Shigella (44%), Salmonella (29%) | ~80-85% | Cannot decide alone; requires a combination |
| eae | Citrobacter, E. albertii | ~85% | Must combine stx + serotype |
| 16S rRNA | Intra-species multi-copy heterogeneity | ~99%+ | Not used for species-level identification |

### Layer 2: ANI whole-genome alignment

#### skani curated panel (`species_mode=panel`)

| Item | Value |
|---|---|
| Database | 284 curated clinical pathogens (Complete Genome / N<500 / no clonal redundancy) |
| Coverage | 72 clinically important pathogens + close-relative controls |
| skani DB | 125 MB (markers.bin + sketches.db + index.db) |
| Runtime | Milliseconds per strain |
| Threshold | ANI ≥95% + AF ≥0.65 → high; 93-95% → medium (border zone) |

**Curated panel construction flow**:

```
NCBI Pathogen Detection tracked list (106 groups)
    ↓ Three rounds of phage removal (839 strains) + N>1000 removal (28 strains)
    ↓ Clinical-importance grading (T1-T4) → quota 2-10 strains/species
    ↓ Intra-species clone removal (redundant ANI ≥99.99% entries dropped)
    ↓ Final panel of 284 strains
```

#### Mash RefSeq sketch (`species_mode=mash_refseq`)

| Item | Value |
|---|---|
| Database | Zenodo community-maintained (159 MB, auto-updated with RefSeq) |
| Runtime | Seconds per strain |
| Threshold | identity ≥0.97 → high; 0.90-0.97 → medium |
| Validation | 17/17 (100%) |

#### skani GTDB full database (`species_mode=skani_gtdb`)

| Item | Value |
|---|---|
| Database | Official pre-sketched GTDB R226 (>140K species representatives) |
| Download | 30 GB compressed / 50 GB unpacked |
| Query RAM | <30 GB |
| Runtime | Milliseconds per strain |
| Use case | Broad-spectrum true ANI (any bacterial species) |

### Layer 3: sourmash gather (`species_mode=sourmash`)

| Item | Value |
|---|---|
| Database | sourmash GTDB RS226 signatures (3.7 GB) |
| Runtime | Seconds per strain |
| Unique value | **Minimal set-cover decomposition** (detects mixed samples/contamination) |

**Mixed-sample rule**: when gather decomposes ≥2 components from different genera, each with containment ≥10% → `possible_mixture` flag, triggering NEEDS_REVIEW.

### Layer 4: GTDB-Tk + CheckM2 (`species_mode=standard`)

| Item | Value |
|---|---|
| GTDB-Tk | v2.7.2 + R232 database (98 GB) |
| CheckM2 | v1.1.0 + DIAMOND DB (3 GB) |
| RAM hard gate | ≥140 GB (setup script refuses if insufficient) |
| Runtime | Minutes to hours |
| Position | Gold-standard arbitration (disputes/regulatory/novel species) |

### Layer 0: Kraken2 reads-level pre-screen (independent switch)

| Item | Value |
|---|---|
| Database | Custom-built (curated panel + GRCh38 + UniVec, ~5 GB) |
| Input | Raw reads (pre-assembly) |
| Runtime | Minutes |
| Value | Earliest contamination/mixture warning + human-read removal (compliance) |

## Cross-Method Arbitration (species_consensus)

### Priority rules

```
gtdbtk (Layer 4) > {skani_gtdb, panel, sourmash, mash_refseq} (Layer 2/3) > marker (Layer 1)
```

| Conflict type | Handling | Example |
|---|---|---|
| Higher vs lower tier disagree | Higher tier overrides lower; conflict recorded but not vetoed | GTDB-Tk says Listeria, marker says Unknown → Listeria |
| **Same-tier** methods conflict | `NEEDS_REVIEW` (manual adjudication) | skani says Salmonella, mash says Vibrio → NEEDS_REVIEW |
| Shigella/EIEC ↔ E. coli | `expected_divergence` (same species, no human review) | Biologically known; GTDB treats them as merged |

### Output

`bio_species_compare` tool consistency matrix:

```
Strain SAM-TYP-001 — species identification method comparison
method       species         confidence
marker       Salmonella      high
panel        Salmonella      high
Verdict: Salmonella (agreement=match, basis=panel)
```

If human review is needed:

```
⚠ NEEDS_REVIEW: same-tier method conflict, manual adjudication required
Conflicting methods: skani_gtdb, sourmash
```

## GOM Evidence Chain

Every identification by every method = an independent ANALYSIS object (immutable, INSERT-ONLY):

```json
{
  "analysis_type": "species_identification",
  "method": "multigene",
  "database": {"name": "markers_v2", "version": "abc12345"},
  "result": {
    "species": "Salmonella",
    "confidence": "high",
    "detected_markers": [{"gene": "invA", "identity": 99.8}]
  }
}
```

Multiple methods coexist: one strain can have marker / panel / mash / GTDB-Tk objects; `bio_species_compare` aggregates them into an arbitration verdict.

## Unified Selection Surface

| Entry | Command |
|---|---|
| config.yaml | `species_mode: simple \| panel \| skani_gtdb \| mash_refseq \| sourmash \| standard` |
| CLI | `run_analysis.py --species-mode panel` |
| Conversation | `bio_db_setup` (tiered deployment) + `bio_species_compare` (view matrix) |
| Deployment | `pixi run setup` or `scripts/setup_databases.py --tier mini` |

**Automatic degradation on missing DB**: if any mode's database is missing → WARNING + fallback to marker-only; the pipeline never breaks.

## Method Selection Guide

| Scenario | Recommended method | Rationale |
|---|---|---|
| Daily surveillance (rapid screening) | `simple` (multigene) | Seconds, zero overhead |
| Routine analysis (confirmed ID) | `panel` (skani panel) | Seconds, true ANI, 125 MB |
| Fast pre-screen (low-spec machines) | `mash_refseq` | 159 MB covers all of RefSeq |
| Broad-spectrum ID (non-target pathogens) | `skani_gtdb` | >140K species covered |
| Mixed-sample investigation | `sourmash` | gather decomposition |
| Dispute arbitration / regulatory review | `standard` (GTDB-Tk) | Gold standard |
| Pre-assembly contamination check | `kraken2_prefilter` | Earliest warning + human-read removal |

## Validation Status

| Method | Validation set | Accuracy | Known limitations |
|---|---|---|---|
| multigene | 17 strains (7 targets + 10 close-relative negatives) | **17/17 (100%)** | C. jejuni/coli markers pending fix |
| skani panel | 17 strains | **17/17 (100%)** | Panel covers 72 species |
| mash_refseq | 17 strains | **17/17 (100%)** | MinHash approximation |
| skani_gtdb | Not downloaded | — | 30 GB |
| sourmash | Not downloaded | — | 3.7 GB |
| GTDB-Tk | Not downloaded | — | Requires 140 GB RAM |

## References

- Jain C, Rodriguez-R LM, Phillippy AM, et al. High throughput ANI analysis of 90K prokaryotic genomes reveals clear species boundaries. *Nat Commun*. 2018;9:5114.
- Shaw J, Yu YW. Fast and robust metagenomic sequence comparison through sparse chaining with skani. *Nat Methods*. 2023;20:1661-1665.
- Chaumeil PA, Mussig AJ, Hugenholtz P, Parks DH. GTDB-Tk v2: memory friendly classification with the Genome Taxonomy Database. *Bioinformatics*. 2022;38(23):5315-5316.
- Pierce NT, Irber L, Reiter T, et al. Large-scale sequence comparisons with sourmash. *F1000Res*. 2019;8:1006.
- Wood DE, Lu J, Langmead B. Improved metagenomic analysis with Kraken 2. *Genome Biol*. 2019;20(1):257.
- Barbau-Piednoir E, et al. SYBR Green qPCR Salmonella detection system. *Appl Microbiol Biotechnol*. 2013;97(12):5271-5279.
- Botteldoorn N, et al. Evaluation of multiplex PCRs for diagnosis of infection with diarrheagenic E. coli and Shigella spp. *J Clin Microbiol*. 2004;42(12):5849-5853.
