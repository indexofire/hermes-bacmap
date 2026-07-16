---
name: ncbi-datasets
description: Use when the user needs to retrieve genomic data, genome metadata, gene information, or taxonomy data from NCBI. Covers genome downloads, gene summaries, sequence retrieval, and metadata export via the NCBI Datasets CLI.
---

# NCBI Datasets

NCBI Datasets provides two CLI tools:
- **`datasets`** — download and summarize biological sequence data (genomes, genes, viruses, taxonomy)
- **`dataformat`** — convert JSON Lines output to TSV or Excel

## Installation

Check if the tools are available before running any commands:

```bash
which datasets && datasets --version
```

If not installed, install via conda:

```bash
conda install -c conda-forge ncbi-datasets-cli
```

Or download the Linux/macOS binary directly from https://ftp.ncbi.nlm.nih.gov/pub/datasets/command-line/v2/

## Core Patterns

### 1. Summarize (metadata only, no download)

```bash
# Genome metadata by taxon
datasets summary genome taxon "Salmonella enterica"

# Genome metadata by accession
datasets summary genome accession GCF_004684285.1

# Gene metadata by symbol and taxon
datasets summary gene symbol rpoB --taxon "Mycobacterium tuberculosis"

# Taxonomy info
datasets summary taxonomy taxon "Bacillus subtilis"
```

### 2. Filter and format output as TSV

Always pipe with `--as-json-lines` when using `dataformat`:

```bash
# Genome metadata as TSV
datasets summary genome taxon "Salmonella enterica" \
  --assembly-source refseq \
  --as-json-lines | dataformat tsv genome \
  --fields accession,assminfo-name,organism-name,assminfo-level,assmstats-total-sequence-len

# Gene metadata as TSV
datasets summary gene symbol invA --taxon "Salmonella" \
  --as-json-lines | dataformat tsv gene \
  --fields gene-id,symbol,description,tax-name
```

### 3. Download a data package

Downloads a `.zip` file containing sequences, annotations, and/or metadata:

```bash
# Download reference genome (FASTA + GFF + metadata)
datasets download genome taxon "Salmonella enterica" \
  --reference \
  --include genome,gff3,rna,cds,protein,seq-report \
  --filename salmonella_enterica.zip

# Download by accession
datasets download genome accession GCF_003197.2 \
  --include genome \
  --filename my_genome.zip

# Extract the downloaded package
unzip my_genome.zip -d my_genome/
```

Downloaded packages contain a `README.md` and data under `ncbi_dataset/data/`.

### 4. Large-scale downloads (dehydrated archives)

For many genomes, use dehydrated archives to avoid re-downloading sequence data:

```bash
# Download dehydrated archive (metadata + manifest, no sequences)
datasets download genome taxon "Pseudomonas" \
  --dehydrated \
  --include genome \
  --filename pseudomonas_dehydrated.zip

unzip pseudomonas_dehydrated.zip -d pseudomonas/

# Rehydrate (fetch actual sequences)
datasets rehydrate --directory pseudomonas/
```

## Common Use Cases

### Get assembly accession for an organism

```bash
datasets summary genome taxon "Salmonella enterica" \
  --reference \
  --as-json-lines | dataformat tsv genome \
  --fields accession,organism-name,assminfo-level
```

### Download a specific gene's sequence

```bash
datasets download gene symbol invA \
  --taxon "Salmonella" \
  --include gene \
  --filename invA_salmonella.zip
```

### List available assembly levels

Use `--assembly-level` to filter: `complete`, `chromosome`, `scaffold`, `contig`

```bash
datasets summary genome taxon "Escherichia coli" \
  --assembly-level complete \
  --as-json-lines | dataformat tsv genome \
  --fields accession,organism-name,assminfo-level
```

### Virus data

```bash
datasets summary virus genome taxon "SARS-CoV-2" --released-after 2023-01-01
datasets download virus genome taxon "influenza" --filename influenza.zip
```

## Key Flags

| Flag | Description |
|------|-------------|---------|
| `--reference` | Only RefSeq reference/representative genomes |
| `--assembly-source refseq\|genbank` | Filter by database source |
| `--assembly-level complete\|chromosome\|scaffold\|contig` | Filter by completeness |
| `--annotated` | Only assemblies with annotation |
| `--released-after MM/DD/YYYY` | Filter by release date |
| `--as-json-lines` | Required when piping to `dataformat` |
| `--include genome,gff3,rna,cds,protein,seq-report` | What to include in download |
| `--api-key <key>` | Use NCBI API key (increases rate limit from 5 to 10 req/s) |

## Output Structure After Unzip

```
ncbi_dataset/
  data/
    <accession>/
      <accession>_<name>_genomic.fna   # genome FASTA
      genomic.gff                       # annotation
      rna.fna                           # RNA sequences
      cds_from_genomic.fna              # CDS sequences
      protein.faa                       # protein sequences
      sequence_report.jsonl             # sequence metadata
  README.md
  md5sum.txt
```

## Notes

- `datasets summary` returns JSON by default; always add `--as-json-lines` before piping to `dataformat`
- API keys can be set via `NCBI_API_KEY` environment variable
- For programmatic/Python use, the `ncbi-datasets-pylib` package wraps the REST API
