# Reference Databases

Hermes-bacmap distributes **15 FASTA databases** in `data/reference/` (subdirectories organized by purpose),
covering species identification, AMR / virulence / plasmid detection, serotyping, SNP reference genomes,
genome annotation, and V. parahaemolyticus serotyping. Databases ship with the repository; BLAST / bwa
indexes must be built on site.

## Species Identification Databases

A five-gene merged library; a single BLAST run completes all species identification (see [Snakemake pipeline · species routing](../architecture/pipeline.md#物种路由五基因系统)).

| File | Size | Sequences | Purpose |
|---|---|---|---|
| `species/markers.fasta` | 8.3 KB | 5 | **Merged library** (invA + uidA + ipaH + toxR + tlh) |
| `salmonella_invA.fasta` | 2.3 KB | 1 | Standalone invA library (M90846.1, 2176 bp) |
| `uidA_ecoli.fasta` | 1.3 KB | 1 | uidA (NC_000913.3, 1190 bp) |
| `ipaH_shigella.fasta` | 1.9 KB | 1 | ipaH (NC_004337.2, 1827 bp) |
| `toxR_vpara.fasta` | 1.3 KB | 1 | toxR (BA000031.2, 643 bp) |
| `tlh_vpara.fasta` | 1.7 KB | 1 | tlh (M36437.1, 1302 bp) |

## AMR / Virulence / Plasmid Databases

Detection runs via abricate under the Snakemake `amr_abricate_*` rules.

| File | Size | Sequences | Source | Detects |
|---|---|---|---|---|
| `amr/card.fasta` | 6.5 MB | ~5,000 | CARD | AMR resistance genes |
| `amr/vfdb.fasta` | 6.3 MB | ~4,000 | VFDB | Virulence factors |
| `plasmid/plasmidfinder.fasta` | 437 KB | ~400 | PlasmidFinder (CGE) | Plasmid replicons |

The `bio_gene_scan` Hermes tool also supports extra databases such as `resfinder` / `ncbi` / `megares` / `victors` / `ecoli_vf` (users must supply the FASTA and build the indexes).

## Serotyping Databases

| File | Size | Sequences | Purpose |
|---|---|---|---|
| `serotype/ecoh.fasta` | 782 KB | 597 | E. coli O/H antigens (ecoh_serotyper) |
| `serotype/shigella.fasta` | 122 KB | 95 | Shigella antigens (shigella_serotyper, ported from ShigATyper) |

The Shigella library supports 58 serotypes: S. flexneri (1a–7b, Y, Yv), S. sonnei (I, II), S. dysenteriae (1–15), S. boydii (1–20).

## SNP Reference Genomes

| File | Size | Contents |
|---|---|---|
| `genomes/salmonella_LT2.fasta` | 4.7 MB | NC_003197.2 (S. enterica LT2 chromosome, 4,857,450 bp) |
| `genomes/ecoli_k12.fasta` | 4.5 MB | NC_000913.3 (E. coli K-12 MG1655, 4,639,675 bp) |
| `genomes/vpara_rimd.fasta` | 5.0 MB | NC_004603.1 + NC_004605.1 (V. parahaemolyticus RIMD 2210633, 5,165,770 bp) |

E. coli + Shigella share the K-12 MG1655 reference (the two are the same species taxonomically). V.para contains 2 chromosomes.

Download:

```bash
# E.coli K-12 MG1655
curl -sL "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/005/845/GCF_000005845.2_ASM584v2/GCF_000005845.2_ASM584v2_genomic.fna.gz" \
  -o /tmp/ecoli.fna.gz && zcat /tmp/ecoli.fna.gz > data/reference/genomes/ecoli_k12.fasta

# V.parahaemolyticus RIMD 2210633
curl -sL "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/196/095/GCF_000196095.1_ASM19609v1/GCF_000196095.1_ASM19609v1_genomic.fna.gz" \
  -o /tmp/vpara.fna.gz && zcat /tmp/vpara.fna.gz > data/reference/genomes/vpara_rimd.fasta

# bwa index
bwa index data/reference/genomes/ecoli_k12.fasta
bwa index data/reference/genomes/vpara_rimd.fasta
samtools faidx data/reference/genomes/ecoli_k12.fasta
samtools faidx data/reference/genomes/vpara_rimd.fasta
```

Chromosomes only; plasmids excluded. Verify before use:

```bash
grep -c "^>" data/reference/genomes/salmonella_LT2.fasta
# 应为 1（单染色体）
```

## V. parahaemolyticus Virulence Databases

| File | Size | Contents |
|---|---|---|
| `virulence/tdh.fasta` | 1.2 KB | tdh (D90238.1, thermostable direct hemolysin) |
| `virulence/trh.fasta` | 1.7 KB | trh (AY586619.1, TDH-related hemolysin) |
| `virulence/vpara_targets.fasta` | 5.7 KB | toxR + tlh merged library |

## BLAST Index Status

The `bio_blast` / `bio_gene_scan` / `species_identify` rules depend on BLAST indexes (`.nhr` / `.nin` / `.nsq`). Indexes must be built on site with `makeblastdb`:

```bash
# 核酸库（物种鉴定 + AMR + 血清型 + SNP 参考 + V.para）
makeblastdb -in data/reference/species/markers.fasta \
    -dbtype nucl -out data/reference/species_markers
makeblastdb -in data/reference/amr/card.fasta \
    -dbtype nucl -out data/reference/card
makeblastdb -in data/reference/amr/vfdb.fasta \
    -dbtype nucl -out data/reference/vfdb
makeblastdb -in data/reference/plasmid/plasmidfinder.fasta \
    -dbtype nucl -out data/reference/plasmidfinder
makeblastdb -in data/reference/serotype/ecoh.fasta \
    -dbtype nucl -out data/reference/ecoh
makeblastdb -in data/reference/serotype/shigella.fasta \
    -dbtype nucl -out data/reference/shigella_ref
makeblastdb -in data/reference/genomes/salmonella_LT2.fasta \
    -dbtype nucl -out data/reference/genomes/salmonella_LT2
makeblastdb -in data/reference/virulence/vpara_targets.fasta \
    -dbtype nucl -out data/reference/vpara_targets
```

Verify:

```bash
ls data/reference/*.nhr
# 应看到每个库对应的 .nhr / .nin / .nsq 三件套
```

## Prokka DBs (for annotation)

The `bio_annotate` and `genome_annotation` rules use pyrodigal to predict CDSs, then annotate them with blastp against the Prokka protein databases. Protein database index:

```bash
# 蛋白库（注意 -dbtype prot）
makeblastdb -in data/reference/annotation/prokka_sprot.fasta \
    -dbtype prot -out data/reference/prokka_sprot
```

Verify:

```bash
ls data/reference/prokka_sprot.phr
# 应存在（蛋白库后缀 .phr / .pin / .psq）
```

If the annotation rate is <30% (all hypothetical proteins), this index is usually missing — just rebuild it. See [Troubleshooting](troubleshooting.md).

## External Databases (optional: standard species identification)

By default, quick species identification uses the built-in target gene libraries (invA/uidA/ipaH/toxR/tlh).
For the standard regime (CheckM2 contamination checking + GTDB-Tk taxonomic validation), the following
databases must be installed externally:

| Database | Size | Environment variable | Purpose | Source |
|---|---|---|---|---|
| CheckM2 DB | ~3 GB | `$CHECKM2DB` | Genome completeness and contamination assessment | [CheckM2 GitHub](https://github.com/chklovski/CheckM2) |
| GTDB-Tk DB | ~70 GB | `$GTDBDB` | Genome-taxonomy-based species identification | [GTDB-Tk GitHub](https://github.com/Ecogenomics/GtDBTk) |

After installation, set the environment variables; the system detects availability automatically:

```bash
export CHECKM2DB=/data/databases/checkm2_db
export GTDBDB=/data/databases/gtdb_r220
```

When not set, `species_mode: standard` automatically falls back to `simple` (target genes only) without errors.

To switch modes, edit `workflows/bacmap/config/config.yaml`:

```yaml
species_mode: standard   # simple（默认）| standard（CheckM2 + GTDB-Tk）
```

Or invoke via natural language through the Hermes Agent:

```
> 用标准方法验证 SAM-TYP-001 的物种    # → bio_validate_taxonomy(mode="standard")
```

## Database Versions and the Evidence Chain

Every ingested ANALYSIS object records database versions into the three-part evidence chain:

```
database_versions:
  CARD: 2026-Apr-3
  VFDB: 2026-Apr-3
  PlasmidFinder: 2026-Apr-3
  PubMLST salmonella_2: <version>
```

Re-ingesting after a database upgrade creates a new version (`create_new_version`); historical versions are retained for traceability. See [GOM · three-part evidence chain](../architecture/gom.md#三元证据链).

## Database Updates

Official update sources for each database:

| Database | Official site | Update frequency |
|---|---|---|
| CARD | <https://card.mcmaster.ca/download> | Quarterly |
| VFDB | <http://www.mgc.ac.cn/VFs/download.htm> | Irregular |
| PlasmidFinder | <https://cge.food.dtu.dk/services/PlasmidFinder.php> | Irregular |
| PubMLST salmonella_2 | <https://rest.pubmlst.org/db/pubmlst_salmonella_seqdef/schemes/2> | Continuous |

After updating: rebuild BLAST indexes → re-run analyses → ingest new versions.

## Related

- [Tool list](tools.md) — `bio_blast` / `bio_gene_scan` depend on these databases
- [Environment setup](../installation/environment.md) — database download and index building steps
- [Snakemake pipeline](../architecture/pipeline.md) — databases used by each rule
- [Troubleshooting](troubleshooting.md) — handling missing-database errors
