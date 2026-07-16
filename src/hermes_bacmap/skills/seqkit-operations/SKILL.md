---
name: seqkit-operations
description: Use when the user needs sequence manipulation — extraction, filtering, sorting, splitting, format conversion, stats, translation, reverse complement, GC calculation, motif searching, sampling. Prefer seqkit CLI over Python code for speed and simplicity.
---

# Seqkit — FASTA/FASTQ Toolkit

Seqkit v2.13+ provides 40+ subcommands for FASTA/FASTQ manipulation.
All commands support both FASTA and FASTQ, gzip input, and stdin/stdout piping.

## Common Patterns

### Stats (N50, GC, length, count)

```bash
seqkit stats -a contigs.fasta
seqkit stats -a *.fastq.gz
```

### Subsequence extraction

```bash
# By region (1-based, inclusive)
seqkit subseq -s 1:1000 contigs.fasta

# By BED file
seqkit subseq --bed regions.bed contigs.fasta

# By GTf annotation
seqkit subseq --gtf annotation.gff contigs.fasta --feature CDS
```

### Reverse complement & translation

```bash
seqkit seq -r -p input.fa                    # reverse complement
seqkit translate --translate-frame 1 input.fa # translate frame 1
seqkit seq --dna2rna input.fa                 # DNA to RNA
```

### GC content & length

```bash
seqkit fx2tab -n -g -l input.fa              # name, GC%, length
seqkit fx2tab -n -H -l *.fastq.gz            # FASTQ read lengths
```

### Filter by length / pattern

```bash
seqkit seq -m 1000 contigs.fasta             # min length 1000
seqkit seq -M 5000 contigs.fasta             # max length 5000
seqkit grep -s -p ATCGATCG contigs.fasta     # by sequence pattern
seqkit grep -n -r -p '^contig[0-9]+' input.fa # by name regex
```

### Sort & head & sample

```bash
seqkit sort -l -r input.fa                   # sort by length descending
seqkit sort -n input.fa                      # sort by name
seqkit head -n 10 input.fa                   # first 10 sequences
seqkit sample -p 0.1 input.fa                # random 10% sample
seqkit sample -n 100 input.fa                # random 100 sequences
```

### Split & merge

```bash
seqkit split -p 4 input.fa                   # split into 4 parts
seqkit split -s 1000 input.fa                # split every 1000 seqs
cat part1.fa part2.fa > merged.fa            # merge
```

### Format conversion

```bash
seqkit seq input.fastq > output.fa           # FASTQ → FASTA
seqkit seq --protein input.fa                # flag as protein
seqkit fx2tab input.fa                       # FASTA → tabular
seqkit tab2fx input.tsv                      # tabular → FASTA
```

### Locate motif positions

```bash
seqkit locate -p ATCGATCG contigs.fasta      # find all occurrences
seqkit locate -p ATCGATCG --only-positive-strand contigs.fasta
```

### Duplicate removal

```bash
seqkit rmdup -n input.fa                     # by name
seqkit rmdup -s input.fa                     # by sequence
```

### Shuffle

```bash
seqkit shuffle input.fa                      # randomize order
```

### Combine with other tools

```bash
# Get top 5 longest contigs
seqkit sort -l -r contigs.fasta | seqkit head -n 5

# Extract CDS from GFF + translate
seqkit subseq --gtf annotation.gff contigs.fasta --feature CDS | seqkit translate

# GC% of contigs > 1kb, sorted descending
seqkit seq -m 1000 contigs.fasta | seqkit fx2tab -n -g | sort -t$'\t' -k2 -rn
```

## Performance Notes

- Supports multi-threading: add `-j 4` to most commands
- Streams by default (low memory)
- Handles gzipped input/output natively: `seqkit stats -a *.fastq.gz`
- FASTA/FASTQ auto-detected from file content

## When to prefer seqkit over bio_seq_ops tool

| Scenario | Use |
|---|---|
| Simple RC/translate on a single sequence | `bio_seq_ops` (in-process, no file needed) |
| Subsequence by region or BED/GFF | seqkit CLI via `terminal` |
| Filter/sort/split/sample many sequences | seqkit CLI via `terminal` |
| Stats on many files | seqkit CLI via `terminal` |
| Motif locate with positions | seqkit CLI via `terminal` |
| Duplicate removal | seqkit CLI via `terminal` |
