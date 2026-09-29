# *Vibrio parahaemolyticus*

## Species Identification

- **Species**: *Vibrio parahaemolyticus*
- **Target genes**: `toxR` + `tlh`
- **toxR**: species-specific transcriptional regulator (BA000031.2)
- **tlh**: thermolabile hemolysin, species marker (M36437.1)
- **Routing rule**: toxR or tlh positive → V. parahaemolyticus pipeline

## Virulence Genes

| Gene | Function | Clinical significance |
|---|---|---|
| `tdh` | thermostable direct hemolysin | Kanagawa phenomenon |
| `trh` | TDH-related hemolysin | Synergistically enhances pathogenicity |
| `tlh` | species marker | Ubiquitous, not directly pathogenic |

## Clinical Interpretation of Virulence Combinations

| tdh | trh | Clinical significance |
|---|---|---|
| + | + | Highly pathogenic, mostly the pandemic clone RIMD 2210633 |
| + | - | Kanagawa positive, gastroenteritis |
| - | + | Gastroenteritis (lower incidence) |
| - | - | Usually an environmental strain, non-pathogenic |

---

## O/K Serotyping

### Overview

VpaSerotyper predicts the O (lipopolysaccharide) and K (capsular polysaccharide) serotypes of *V. parahaemolyticus* from assembled contigs.
The engine is ported from [vpautils](https://github.com/indexofire/vpautils) and uses a Kaptive-style three-stage algorithm.

### Algorithm Pipeline

```
Assembled contigs
    |
A. minimap2 alignment -> extract locus-region contigs
    |
B. sourmash k-mer containment -> rank candidate loci
    |
C. gene-level verification -> per-gene coverage/identity
    |
D. decision -> confidence tier (Perfect/High/Medium/Low/Unknown)
```

| Stage | Method | Purpose |
|---|---|---|
| A. Locus extraction | minimap2 (mappy) splice mode | Extract the regions of sample contigs aligned to reference loci |
| B. K-mer ranking | sourmash MinHash containment | Rapidly shortlist the best-matching reference loci (>30% containment) |
| C. Gene verification | minimap2 per-gene alignment | Coverage and identity of each reference gene in the sample |
| D. Confidence decision | Rule engine | Integrates missing-gene count, coverage, identity, boundary genes, fragmentation |

### Confidence Tiers

| Tier | Condition | Meaning |
|---|---|---|
| **Perfect** | Single contig + 0 missing + identity > 95% | Complete match, high-confidence typing |
| **High** | <=1 missing + coverage > 90% + identity > 90% | High confidence, reportable |
| **Medium** | <=4 missing + identity > 80% | Medium confidence, reportable with caveats |
| **Low** | identity > 80% (via the other conditions) | Low confidence, supplementary verification recommended |
| **Unknown** | >4 missing or boundary genes missing | Untypeable |

### Reference Database

```
data/reference/vpa_serotype/ (33 MB)
├── ref_seqs.fasta      7.0 MB   195 reference locus sequences
├── gene_refs.fasta     6.4 MB   gene-level reference sequences
├── ref_sketches.sig    1.4 MB   sourmash MinHash signatures (k=21, scaled=100)
├── ref_meta.pkl        518 KB   locus metadata (gene positions, types, names)
├── ref_meta.sig        64 B     HMAC signature (integrity check)
├── OAgc.gbk            1.8 MB   O-antigen gene cluster GenBank source
└── CPSgc.gbk           16 MB    K-capsule gene cluster GenBank source
```

| Type | Loci | Examples |
|---|---|---|
| O-antigen (OL) | 32 | OL1, OL2, OL3, OL4, OL5, ... OL11, ... |
| K-antigen (KL) | 163 | KL1, KL6, KL12, KL15, KL28, ... |

### Usage

#### Command Line (Snakemake)

```bash
# Single sample (auto-triggers assembly -> serotyping)
python scripts/run_analysis.py --sample SAM-VPA-001
```

Snakemake automatically executes the `vpara_serotype` rule, writing output to:
```
results/{sample}/vpa/vpa_serotype.json
```

#### Hermes Agent

```
hermes chat
> perform serotyping on the SAM-VPA-001 contigs
```

Invokes the `bio_vpa_serotype` tool and returns the JSON result.

#### Python API

```python
from hermes_bacmap.typing.vpa_serotyper import VpaSerotyper

s = VpaSerotyper()
result = s.analyze("contigs.fasta", "SAM-VPA-001")

print(result.predicted_serotype)  # "O3:K6"
print(result.o_confidence)        # "Perfect"
print(result.k_confidence)        # "Perfect"
```

### Output Field Reference

#### SerotypeResult basic fields

| Field | Type | Description | Example |
|---|---|---|---|
| `sample` | str | Sample ID | SAM-VPA-001 |
| `predicted_serotype` | str | Predicted serotype | O3:K6 |
| `o_locus` | str | Best-matching O-antigen locus | OL3 |
| `o_confidence` | str | O confidence | Perfect |
| `o_coverage` | float | O gene coverage (%) | 100.0 |
| `o_identity` | float | O mean identity (%) | 100.0 |
| `o_missing_genes` | str | O missing genes (semicolon-separated) | None |
| `o_alerts` | str | O alerts | None |
| `k_locus` | str | Best-matching K-antigen locus | KL6 |
| `k_confidence` | str | K confidence | Perfect |
| `k_coverage` | float | K gene coverage (%) | 100.0 |
| `k_identity` | float | K mean identity (%) | 99.98 |
| `k_missing_genes` | str | K missing genes | None |
| `k_alerts` | str | K alerts | None |

#### Detailed engine output (enable_detail=True)

| Field | Description |
|---|---|
| `O/K_Expected_In_Locus` | Number/percentage of gene hits on the expected locus contig |
| `O/K_Expected_Outside` | Number of gene hits outside the locus (on other contigs) |
| `O/K_Other_In_Locus` | Genes of other loci appearing in the locus region (possible recombination) |
| `O/K_Truncated` | List of genes with coverage <100% |
| `O/K_Length_Discrepancy` | Sample locus total length - reference length (negative = loss) |
| `O/K_Genes_Detail` | identity/coverage/status per gene |
| `O/K_Detail` | Engine diagnostic notes (when confidence is not Perfect) |
| `_gene_details` | Per-gene detail dict (gene, identity, coverage, status, contig, position) |

#### Alert types

| Alert | Meaning |
|---|---|
| `Fragmented` | Locus spans multiple contigs (incomplete assembly) |
| `MissingBoundary(gene1,gene2)` | Boundary genes missing (coaD/rfaD/glpX), making the locus untypeable |

### Validation Results

#### RIMD 2210633 (O3:K6 global pandemic strain)

| Metric | O antigen (OL3) | K antigen (KL6) |
|---|---|---|
| Confidence | Perfect | Perfect |
| Gene coverage | 26/26 (100%) | 31/31 (100%) |
| Mean identity | 100.00% | 99.98% |
| Missing genes | None | None |
| Length discrepancy | 0 bp | 0 bp |
| Runtime | <1s | <1s |

#### Batch validation (10 strains)

| Sample | Expected | Predicted | Correct |
|---|---|---|---|
| GCA_000706825.2 | O4:K12 | O4:K12 | OK |
| GCA_000706905.2 | O4:K12 | O4:K12 | OK |
| GCA_000707185.2 | O3:K12 | O3:K12 | OK |
| GCA_000707465.2 | O11:K15 | O11:K15 | OK |

**Accuracy: 4/4 known serotypes = 100%, averaging 2.6 seconds per strain.**

### Complex Sample Diagnosis Example

The K antigen of GCA_000707465.2 (O11:K15) was reported with Medium confidence:

| Dimension | Value | Notes |
|---|---|---|
| Missing genes | KL15_022, 023, 024, 025 | 4 consecutive genes missing |
| Length discrepancy | -4855 bp | K locus is 4855 bp shorter than the reference |
| Truncated genes | KL15_002 (85.9%), KL15_018 (81.8%) | Some genes incomplete |
| Foreign gene intrusion | 8 | Possible recombination |

The engine correctly identified K15, but the missing genes lowered the confidence.

### Dependencies

| Dependency | Version | Purpose |
|---|---|---|
| `mappy` (minimap2) | >= 2.24 | Python binding, sequence alignment |
| `sourmash` | >= 4.8 | MinHash k-mer containment |
| `ref_seqs.fasta` + index | — | minimap2 reference sequences |
| `ref_sketches.sig` | — | sourmash signatures |
| `ref_meta.pkl` | — | locus metadata |

### Hermes Tool

| Property | Value |
|---|---|
| Tool name | `bio_vpa_serotype` |
| Input | contigs_path (FASTA) |
| Output | JSON (SerotypeResult) |
| Description | Predicts the V. parahaemolyticus O/K serotype |

### Snakemake Rule

```python
rule vpara_serotype:
    input:
        contigs = "{sample}/assembly/contigs.fasta"
    output:
        result = "{sample}/vpa/vpa_serotype.json"
```

Example output JSON:
```json
{
  "sample": "RIMD2210633",
  "predicted_serotype": "O3:K6",
  "o_locus": "OL3",
  "o_confidence": "Perfect",
  "o_coverage": 100.0,
  "o_identity": 100.0,
  "o_missing_genes": "None",
  "o_alerts": "None",
  "k_locus": "KL6",
  "k_confidence": "Perfect",
  "k_coverage": 100.0,
  "k_identity": 99.98,
  "k_missing_genes": "None",
  "k_alerts": "None"
}
```

---

## MLST

- **Scheme**: PubMLST *V. parahaemolyticus*
- **Loci**: `dnaE`, `gyrB`, `recA`, `dtdS`, `pntA`, `pyrC`, `tnaA`
- **Tool**: `gmlst`

## AMR

- Uses abricate (CARD / VFDB / PlasmidFinder)
- Clinical V. parahaemolyticus strains are usually susceptible to most antibiotics; AMR genes are relatively rare
