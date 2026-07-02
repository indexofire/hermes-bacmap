---
name: bioinfo-analysis
description: >
  Generic bioinformatics analysis pipelines and decision tree for choosing tools
  (variant calling, RNA-seq, long-read, sequence identification). Load when user
  asks about analysis types NOT covered by the pathogen pipeline, or needs help
  choosing between bio_blast/bio_align/bio_variant/bio_samtools tools.
  Trigger words: pipeline, variant calling, RNA-seq, long-read, minimap2, bwa.
version: 0.1.0
metadata:
  hermes:
    tags: [bioinformatics, genomics, sequencing, ngs, variant-calling]
---

# Bioinformatics Analysis Guide

This skill provides decision trees and common pipeline templates for the
bioinfo plugin tools. Load this when planning a sequencing analysis.

## Decision Tree: What Tool to Use First

```
Input is...                         → First action
─────────────────────────────────────┼──────────────────────────
FASTQ reads (raw)                   → bio_fastq_qc  (quality triage)
FASTA assembly / contigs            → bio_seq_stats (N50, GC)
Single sequence (unknown origin)    → bio_blast     (identification)
BAM file (already aligned)          → bio_samtools flagstat
VCF file                            → bio_variant query
```

## Pipeline 1: Whole-Genome Resequencing (Variant Calling)

1. **QC**: `bio_fastq_qc` on raw FASTQ — check Q30, adapters
2. **Align**: `bio_align` with aligner=bwa-mem, reference → sorted BAM
3. **Stats**: `bio_samtools` operation=flagstat — verify mapping rate >90%
4. **Call**: `bio_variant` operation=mpileup_call — BAM + reference → VCF
5. **Filter**: `bio_variant` operation=filter — QUAL>30, DP>10
6. **Annotate**: `bio_variant` operation=annotate — add functional annotations

## Pipeline 2: Long-Read Sequencing (ONT/PacBio)

1. **QC**: `bio_fastq_qc` — long reads, check N50
2. **Align**: `bio_align` aligner=minimap2, preset=map-ont (ONT) or map-pb (PacBio)
3. **Call**: `bio_variant` operation=mpileup_call — or use specialized long-read caller

## Pipeline 3: RNA-seq (Differential Expression)

1. **QC**: `bio_fastq_qc`
2. **Align**: `bio_align` aligner=minimap2 preset=splice OR STAR (via terminal)
3. **Count**: Use `terminal` to run featureCounts / htseq-count
4. **DE analysis**: Use `execute_code` with DESeq2/edgeR (R) or Python equivalents

## Pipeline 4: Sequence Identification / Homology

1. `bio_blast` mode=remote — query NCBI nr/nt database
2. `bio_seq_ops` operation=translate — check protein-coding potential
3. `bio_seq_ops` operation=find_orfs — find all open reading frames
4. `bio_seq_ops` operation=motif_search — check for regulatory motifs

## Common File Format Conventions

| Extension | Format      | Tool support |
|-----------|-------------|--------------|
| .fasta/.fa/.fna/.faa | FASTA | All tools |
| .fastq/.fq | FASTQ | qc, convert |
| .gb/.gbk   | GenBank    | stats, convert |
| .bam       | BAM        | samtools, variant |
| .vcf       | VCF        | variant |
| .bed       | BED        | (via terminal/bedtools) |

## External Tool Dependencies

The plugin auto-detects these at runtime. Missing tools produce clear errors:

| Tool | Install |
|------|---------|
| Biopython | `pip install biopython` (auto-attempted on first use) |
| samtools | `conda install -c bioconda samtools` |
| bwa | `conda install -c bioconda bwa` |
| minimap2 | `conda install -c bioconda minimap2` |
| bcftools | `conda install -c bioconda bcftools` |
| blast+ | `conda install -c bioconda blast` |

## Tips

- Always start with `bio_seq_stats` or `bio_fastq_qc` — never skip QC.
- For large genomes (>100Mb), use `sample_reads` in QC to speed up.
- BAM files from `bio_align` are sorted + indexed by default — ready for IGV.
- Use `bio_seq_convert` to convert GenBank→FASTA before alignment tools.
- BLAST remote queries NCBI servers — can be slow (30-120s). Use local DB for speed.
