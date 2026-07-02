# Salmonella Pipeline Parameters

## Snakemake Configuration

| Parameter | Default | Config Key |
|---|---|---|
| Threads | 8 | `--cores` |
| Min contig length | 200 | assembly rule |
| invA identity threshold | 90% | species rule |
| invA coverage threshold | 80% | species rule |
| abricate min identity | 80% | amr rules |
| abricate min coverage | 80% | amr rules |
| SNP QUAL filter | 30 | snp_matrix script |
| IQ-TREE model | GTR+UFBoot1000 | phylo_tree rule |

## Assembly Quality Thresholds

| Metric | Good | Acceptable | Poor |
|---|---|---|---|
| N50 | >100kb | 10-100kb | <10kb |
| Total contigs | <100 | 100-500 | >500 |
| Total length | 4.5-5.5 Mb | 4-6 Mb | <4 Mb or >6 Mb |
| GC content | 50-53% | 48-55% | <48% or >55% |

## Expected Analysis Time (8 threads)

| Step | Time | RAM |
|---|---|---|
| fastp QC | 1-2 min | 1-2 GB |
| Shovill assembly | 30-60 min | 8-16 GB |
| species_id (BLAST) | <1 min | <1 GB |
| gmlst | 1-2 min | <1 GB |
| SISTR | <1 min | <1 GB |
| abricate (3 DBs) | 2-3 min | <4 GB |
| SNP calling (per sample) | 4-10 min | 8-16 GB |
| Annotation (pyrodigal + blastp) | 2-3 min | 2-4 GB |
