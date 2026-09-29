# Pathogen Analysis Overview: Pipelines, Capabilities, and Implementation

This document is an **implementation-level overview** of the analysis of the 4 foodborne pathogens: the complete analysis-pipeline DAG,
the capability matrix for each pathogen, and the concrete implementation of every capability (rule → tool → code module → database → output).
For the biological background of each pathogen and the interpretation of results, see the individual chapters:

- [Salmonella](salmonella.md) · [DEC / E. coli](dec.md) · [Shigella / EIEC](shigella.md) · [V. parahaemolyticus](vpara.md)

---

## 1. Analysis Pipeline Panorama

### 1.1 Per-sample main pipeline (per-sample DAG)

All pathogens share one main pipeline, entered via `workflows/bacmap/Snakefile`; the targets of `rule all` are, per strain,
`{sample}_summary.json` + `annotation.json` + `vpa_serotype.json` (+ cohort aggregation).

| # | Rule (file) | Tool | Input → Output | Notes |
|---|---|---|---|---|
| 1 | `qc_fastp` (qc.smk) | fastp | raw FASTQ → clean FASTQ (temp) + fastp.json/html | Q20 filtering, length ≥50, automatic adapter detection |
| 2 | `assembly_shovill` (assembly.smk) | Shovill (SPAdes) | clean FASTQ → contigs.fasta | minlen 500 / ram 8 / depth 100 |
| 3 | `assembly_stats` (assembly.smk) | seqkit stats | contigs → assembly_stats.tsv | Assembly quality statistics |
| 4 | `species_identify` (species.smk) | Python `species_identifier` + BLAST | contigs → species_id.json | One BLAST run over the 5 marker genes, routed by result (see §2) |
| 5 | `taxonomy_validation` (taxonomy.smk) | Python `taxonomic_validator` | contigs → validation.json | simple mode (markers) / standard mode (CheckM2 completeness + contamination, GTDB-Tk taxonomy) |
| 6 | `genome_annotation` (annotation.smk) | pyrodigal + blastp (Prokka DBs) | contigs → annotation.json | Pure-Python CDS prediction + sprot/amr/is annotation |
| 7 | `typing_mlst` (typing_amr.smk) | gmlst | contigs → mlst.tsv | Classic 7-gene MLST, scheme auto-selected per species |
| 8 | `typing_sistr` (typing_amr.smk) | SISTR | contigs → sistr.json + sistr_cgmlst.csv | Salmonella serotype (incl. mash + cgMLST typing) |
| 9 | `amr_abricate_vfdb` (typing_amr.smk) | abricate | contigs → abricate_vfdb.tsv | Virulence genes (minid 80 / mincov 60) |
| 10 | `amr_abricate_card` (typing_amr.smk) | abricate | contigs → abricate_card.tsv | AMR resistance genes |
| 11 | `amr_abricate_plasmidfinder` (typing_amr.smk) | abricate | contigs → abricate_plasmidfinder.tsv | Plasmid replicons |
| 12 | `amr_amrfinderplus` (typing_amr.smk) | NCBI AMRFinderPlus | contigs → amrfinderplus.tsv | Adds `--organism` per species (see §3.6) |
| 13 | `dec_ecoh_serotype` / `dec_pathotype` / `shigella_serotype` (dec_shigella.smk) | Python `typing/` modules | contigs / vfdb → ecoh_serotype.json / pathotype.tsv / shigella_serotype.json | DEC- and Shigella-specific (see §4.2/§4.3) |
| 14 | `vpara_targets` / `vpara_virulence` / `vpara_serotype` (vpara.smk) | blastn + Python `typing/` modules | contigs → targets_blastn.tsv / virulence.json / vpa_serotype.json | V. parahaemolyticus-specific (see §4.4) |
| 15 | `report_summary` (report.smk) | `scripts/collect_summary.py` | The above 15 artifacts → `{sample}_summary.json` | Aggregated into a single JSON — the data source for GOM ingestion and reports |

### 1.2 Species routing mechanism

**There is no standalone routing rule** — routing is embedded in two places:

1. **Sample-sheet pre-declaration**: the `species` column of `config/samples.tsv` (`Salmonella` / `E.coli` / `Shigella` / `V.parahaemolyticus`)
   determines every `lambda wc:` parameter selection, such as MLST scheme, AMRFinderPlus organism, and SNP grouping.
2. **Post-assembly verification**: `species_identify` runs **one** BLAST of the 5 marker genes against the `species_markers` database
   (identity ≥85%, coverage ≥30%) and calls the species from the first hit under the priority order `invA > ipaH > toxR > tlh > uidA`
   (`analysis/species_identifier.py`), cross-checked against the sample-sheet declaration.
   Adding a new pathogen only requires adding genes to `markers.fasta` + registering them in `_GENE_TO_SPECIES` — no rule changes needed.

### 1.3 Cohort SNP pipeline (auto-triggered at ≥2 strains of the same species)

`snp.smk` splits samples into three species groups; each group independently produces a phylogeny:

| Group | Reference genome | Species covered |
|---|---|---|
| `salmonella` | *S. enterica* LT2 (salmonella_LT2.fasta) | Salmonella |
| `ecoli` | *E. coli* K-12 MG1655 (ecoli_k12.fasta) | E.coli + Shigella (the same species taxonomically; shared reference) |
| `vpara` | RIMD 2210633 (vpara_rimd.fasta) | V.parahaemolyticus |

Pipeline: `snp_calling` (bwa mem -Y -M + samtools sort → BAM) → `joint_variant_calling` (bcftools mpileup -q20 -Q20 --max-depth 200 | call -mv --ploidy 1, joint calling within a group)
→ `snp_matrix` (VCF → core_snps.fasta whole-genome SNP matrix)
→ `phylo_tree` (IQ-TREE GTR; -bb 1000 -alrt 1000 UltraFast Bootstrap for ≥4 strains) → `snp_summary` (distance matrix + Newick → snp_summary.json).

### 1.4 cgMLST trace-back pipeline (off by default, opt-in)

`cgmlst.smk`, enabled by `config.cgmlst.run_cgmlst_cohort: true` (when false — the default — the 4 cohort rules **do not enter the DAG**):

- `typing_cgmlst` (always on): gmlst types against the EnteroBase cgMLST schemes — senterica_2 (3002 loci) / ecoli_2 (2513) / vparahaemolyticus_3 (2254).
- Cohort chain: `cgmlst_cohort_profiles` (merges per-sample TSVs within a group) → `cgmlst_distance_matrix` (Hamming allelic distance:
  **counted only over loci called in both genomes**; a locus missing on either side is excluded, per the EnteroBase HierCC convention)
  → `cgmlst_mst` (GrapeTree-style minimum spanning tree, scipy; nj optional) → `cgmlst_summary`.
- **Trace-back projection**: `analysis/cgmlst_projection.py` compares query strains against the local reference library, takes the top 10 nearest by Hamming distance,
  and issues `OUTBREAK / RELATED / UNRELATED / UNDETERMINED` calls using per-species published thresholds (thresholds and literature sources in §5.2).

### 1.5 Fault-tolerance design

All calling-type rules carry a fallback (`|| echo '<placeholder JSON>' > output`): species, MLST, SISTR, ecoh/shigella/vpa serotyping, taxonomy,
and amrfinderplus (`|| touch`) write a structured placeholder result on failure instead of aborting the pipeline — guaranteeing that the 15 inputs
to `report_summary` are always available and that a failed step can be re-run afterwards (Snakemake checkpoint resume).
abricate and assembly-type rules have no fallback (a failure is a failure, i.e. a hard error).

---

## 2. Capability matrix of the four pathogens

| Capability | Salmonella | DEC (E. coli) | Shigella / EIEC | V. parahaemolyticus |
|---|---|---|---|---|
| Species identification marker | invA | uidA | ipaH | toxR + tlh |
| Standard taxonomic validation | GTDB-Tk / CheckM2 (standard mode) | same | same | same |
| Serotype | **SISTR** (serovar/serogroup/O/H) | **ecoh_serotyper** (O:H, Python) | **shigella_serotyper** (58 types, Python) | **VpaSerotyper** (O/K, Python) |
| Pathotype | — | **call_pathotype** (STEC/EPEC/ETEC/EIEC/EAEC) | EIEC marker hint (EclacY + ipaH) | — |
| MLST (classic) | salmonella_2 | ecoli_1 | ecoli_1 | vparahaemolyticus_1 |
| cgMLST | senterica_2 | ecoli_2 | ecoli_2 | vparahaemolyticus_3 |
| AMR | abricate CARD + AMRFinderPlus (--organism Salmonella) | abricate CARD + AMRFinderPlus (--organism Escherichia) | same as DEC | abricate CARD + AMRFinderPlus (no organism) |
| Virulence | abricate VFDB | abricate VFDB (doubles as the pathotype input) | abricate VFDB | abricate VFDB + **dedicated tdh/trh BLAST** |
| Plasmid | abricate PlasmidFinder | same | same | same |
| SNP/phylogeny | bwa+bcftools+iqtree vs LT2 | vs K-12 (grouped with Shigella) | vs K-12 (grouped with E.coli) | vs RIMD |
| cgMLST trace-back thresholds | 10/3/50 (published values) | 5/50 + serotype-specific | 5/50 (sonnei requires SNV confirmation) | **no published values → UNDETERMINED** |
| Annotation | pyrodigal + Prokka DBs | same | same | same |

---

## 3. Implementation details of the shared capabilities (common to the 4 pathogens)

### 3.1 Quality control and assembly

fastp parameters come from `config.yaml:tools.fastp`; Shovill wraps SPAdes and brings its own read correction and contig filtering.
Clean reads are marked `temp` — deleted automatically once SNP calling completes; contigs.fasta is the sole input for all subsequent
assembly-based analyses.

### 3.2 Species identification (`analysis/species_identifier.py`)

`identify(contigs)` delegates to `gene_scanner.scan(db_name="species_markers")` (which underneath goes through engine.SequenceMatcher → the
blastn backend), takes the best hit per marker, outputs `detected_markers` sorted by `_SPECIES_PRIORITY`, and calls species + confidence.
Thresholds: identity ≥85%, coverage ≥30% (lenient — marker genes are highly conserved, so the broad-in/strict-out strategy relies on
priority arbitration).

### 3.3 Taxonomic validation (`analysis/taxonomic_validator.py`)

`validate_genome(contigs, mode)`: `simple` mode performs marker identification only; `standard` mode additionally runs CheckM2
(completeness/contamination, requires the `CHECKM2DB` environment variable) and GTDB-Tk (taxonomic assignment, requires the GTDB database).
When tools or databases are missing it degrades to skip and records the reason instead of failing.

### 3.4 Genome annotation (`analysis/genome_annotator.py`)

pyrodigal performs CDS prediction (100% equivalent to Prodigal) and blastp annotates against the three Prokka databases (sprot/amr/is),
replacing the Perl-dependency-heavy Prokka CLI. Outputs annotation.json (CDS + annotations + statistics).

### 3.5 MLST (`typing_mlst`)

A single gmlst invocation completes typing; the scheme is mapped from the sample-sheet species (`_GMLST_SCHEMES`): Salmonella→salmonella_2,
E.coli/Shigella→ecoli_1, V.para→vparahaemolyticus_1. On failure, an `ST=N/A` placeholder is written.

### 3.6 AMR / virulence / plasmid (abricate ×3 + AMRFinderPlus)

- Unified parameters for the three abricate databases: `--minid 80 --mincov 60` (adjustable in config). CARD = resistance, VFDB = virulence,
  PlasmidFinder = plasmid replicons.
- AMRFinderPlus adds the organism flag per species (Salmonella→`--organism Salmonella`, E.coli/Shigella→`--organism Escherichia`,
  V.para none — there is no official organism library), with `--coverage_min 0.5`; the database is the newest version directory under
  `data/db/amrfinderplus`.

### 3.7 Generic gene-scanning engine (`analysis/gene_scanner.py` + `engine/`)

All Python calling modules (species/ecoh/shigella) do not call BLAST directly but delegate to gene_scanner → engine.SequenceMatcher
(automatic backend selection: blastn for small files, minimap2 for >10MB; blastp for proteins).
Databases are registered by name (`species_markers` / `ecoh` / `shigella_ref` / ...), each backed by a FASTA under `data/reference/`.
This is the abstraction layer of "swap the backend without touching business code".

---

## 4. Pathogen-specific implementations

### 4.1 Salmonella

| Item | Implementation |
|---|---|
| Species | invA marker (priority 1) |
| Serotype | SISTR: `sistr -MM --more-results --run-mash`, outputs serovar / serogroup / o_antigen / h1 / h2 + a cgMLST typing CSV; SISTR also runs its own mash species cross-check |
| MLST | salmonella_2 (aroC/dnaN/hemD/hisD/purE/sucA/thrA) |
| AMR | Dual engine: abricate CARD + AMRFinderPlus (organism-specific, includes point-mutation resistance) |
| SNP | vs LT2 (NC_003197.2) |

### 4.2 DEC (diarrheagenic *E. coli*)

| Item | Implementation |
|---|---|
| Species | uidA marker |
| Serotype | `typing/ecoh_serotyper.py`: scans the ecoh database, regex-parses O-antigen genes (wzx/wzy/wzm/wzt-O*n*) and H-antigen genes (fliC/flkA/fllA/flmA/flnA-H*n*), scores each antigen type as `identity × coverage / 100` and takes the maximum → `O{n}:H{n}`. No O antigen outputs `-` (e.g. the frequent loss in O157 STEC) |
| **Pathotype** | `scripts/call_pathotype.py`, input is the vfdb result; rules evaluated in declaration order with **multiple hits** possible: stx1/stx2→STEC; ipaH family (ipaH/ipaB/ipaC/ipaD/ipaJ/ipgC/mxi etc.)→EIEC/Shigella; eae+bfpA (all)→tEPEC; eae→aEPEC; est/elt/STh/STp/LT→ETEC; aggR/aatA/aaiC→EAEC; all negative→Non-pathogenic |
| MLST | ecoli_1; SNP grouped with Shigella (K-12 reference) |

### 4.3 Shigella / EIEC

| Item | Implementation |
|---|---|
| Species | ipaH marker (multi-copy, highest sensitivity) |
| Serotype | `typing/shigella_serotyper.py` (ported from CFSAN ShigATyper, 58 types); scans the shigella_ref database and calls from gene combinations:<br>· *S. flexneri*: Sf6_wzx→type 6; gtr gene combinations (gtrI/II/IV/V/X/IC + Oac/Oac1b + Xv) **exact match**→high; Oac variants→medium; near matches off by one gene→medium; Sf_wzx/wzy without gtr→type Y; unknown combination→"novel serotype" (low)<br>· *S. sonnei*: Ss_wzx+wzy double positive→high<br>· *S. dysenteriae* 1–15 / *S. boydii* 1–20: wzx+wzy double positive→high, single positive→medium, SdProv/SbProv→untypeable<br>· Multiple species signals at once→suspected contamination/assembly error (low)<br>· **EIEC differentiation hint**: EclacY (E. coli marker) + ipaH detected → annotated "may be EIEC rather than Shigella" |
| Relation to DEC | ipaH-positive samples also run ecoh_serotyper + pathotype (EIEC/Shigella pathotype); the three lines of evidence are interpreted jointly |

### 4.4 V. parahaemolyticus

| Item | Implementation |
|---|---|
| Species | `vpara_targets`: standalone BLAST (evalue 1e-50, word_size 28) against the vpara_targets database, three-state calling — hit containing toxR/tlh → `V_parahaemolyticus`; hit without toxR/tlh → `ambiguous_vpara`; no hit → `not_V_parahaemolyticus` (written to species_verdict.txt) |
| Virulence | `vpara_virulence`: per-gene BLAST of tdh/trh/tlh → boolean virulence.json (tdh+trh combination interpretation in [vpara.md](vpara.md)) |
| Serotype | `typing/vpa_serotyper.py` + `vpa_serotyper_engine.py` (ported from vpautils, Kaptive-style four stages):<br>A. minimap2 (mappy) extracts the locus regions from contigs → B. sourmash MinHash containment ranks candidate O/K loci (>30%) → C. per-gene coverage/identity verification → D. a rule engine assigns the confidence (Perfect/High/Medium/Low/Unknown), reporting missing genes and alerts. Defaults to `OUT:KUT` (untypeable)<br>Database: `data/reference/vpa_serotype/` (gene_refs + ref_seqs + ref_meta.pkl + CPS/O-antigen GenBank) |
| Trace-back | the cgMLST scheme vparahaemolyticus_3 can run, but there are **no published outbreak thresholds** → the trace-back call is always UNDETERMINED (local calibration required, see §5.2) |

---

## 5. Output artifacts and parameter quick reference

### 5.1 Results directory layout

```
results/
├── {sample}/
│   ├── qc/            fastp.json / fastp.html (clean reads are temp)
│   ├── assembly/      contigs.fasta / assembly_stats.tsv
│   ├── species/       species_id.json
│   ├── taxonomy/      validation.json
│   ├── annotation/    annotation.json
│   ├── typing/        mlst.tsv / sistr.json / sistr_cgmlst.csv / cgmlst.tsv
│   ├── amr/           abricate_card.tsv / abricate_vfdb.tsv / amrfinderplus.tsv
│   ├── plasmid/       abricate_plasmidfinder.tsv
│   ├── dec/           ecoh_serotype.json / pathotype.tsv / shigella_serotype.json
│   ├── vpara/         targets_blastn.tsv / species_verdict.txt / virulence.json
│   ├── vpa/           vpa_serotype.json
│   ├── snp/           snps.bam
│   └── report/        {sample}_summary.json          ← GOM ingestion + HTML report data source
├── snp/{group}/       joint.vcf.gz / core_snps.fasta / core.treefile / snp_summary.json
└── cgmlst/{group}/    cgmlst_profiles.tsv / distance_matrix.json / core.treefile / cgmlst_summary.json
```

### 5.2 cgMLST trace-back thresholds (config.yaml, all with literature sources)

| Species | outbreak | clonal | related | Source |
|---|---|---|---|---|
| Salmonella | ≤10 | ≤3 | ≤50 | Zhou 2020 Genome Res (HC5/HC10, HC50); Ferrato 2023 (ST11/ST34) |
| E.coli | ≤5 | — (serotype-specific: O26:H11=8 / O157:H7=16 / O103:H2=5 / O80:H2=9) | ≤50 | Emerjean 2025 CDC EID; Zhou 2020 |
| Shigella | ≤5 | — | ≤50 | Hawkey 2021 Nat Commun; **S. sonnei requires SNV confirmation** |
| V. parahaemolyticus | null | — | null | No published thresholds (Achtman 2022 gives only the HC1090 species boundary) → UNDETERMINED |

Distance definition: the number of allelic differences counted over loci missing in neither genome (HierCC convention).

### 5.3 Key tool parameters (config.yaml)

| Tool | Parameters |
|---|---|
| fastp | qualified_quality_phred=20, length_required=50, detect_adapter_for_pe |
| Shovill | minlen=500, ram=8, depth=100 |
| abricate | minid=80, mincov=60 |
| AMRFinderPlus | coverage_min=0.5, organism per species |
| blastn (vpara-specific) | evalue=1e-50, word_size=28 |
| bcftools mpileup | -q 20 -Q 20 --max-depth 200 |
| IQ-TREE | -m GTR; add -bb 1000 -alrt 1000 for ≥4 strains |

---

## 6. AI-layer entry points

Analysis capabilities are exposed to the LLM through 27 Hermes tools (table-driven registration in `tools/registry.py`);
those directly related to analysis include:

| Tool | Function |
|---|---|
| `bio_analyze_pathogen` | End-to-end orchestration (equivalent to `scripts/run_analysis.py --sample`) |
| `bio_get_result` / `bio_verify_result` | Read summary / deterministic rule verification (three-layer defense, Layer 2) |
| `bio_gene_scan` | Gene scanning against any reference database (direct passthrough to gene_scanner) |
| `bio_snp_tree` / `bio_cgmlst` | Cohort SNP / cgMLST trace-back queries |
| `bio_vpa_serotype` | Standalone V. para serotype call |
| `bio_validate_taxonomy` / `bio_annotate` | Taxonomy validation / annotation |
| `bio_search_samples` / `bio_query_metadata` | GOM retrieval (FTS5) |
| `bio_generate_report` / `bio_diagnose` |
| `bio_species_compare` | Cross-method species identification consistency matrix + arbitration verdict | HTML/PDF reports / failure diagnostics (9 error modes) |

---

*Implementation corresponds to version V0.7 (2026-09). Rule count: 11 rule files / 29 rules (25 regular + 4 cgMLST cohort-gated) + `rule all`.*
