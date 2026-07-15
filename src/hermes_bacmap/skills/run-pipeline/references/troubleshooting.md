# Pipeline Troubleshooting

## Snakemake Lock Error

```
Error: Directory cannot be locked. Please make sure that nothing else uses the directory.
```

Fix: `cd workflows/bacmap && snakemake --unlock`

## Shovill OOM

```
Error: signal 9 (SIGKILL) — out of memory
```

Fix: Reduce threads or memory: `python scripts/run_analysis.py --sample SAM-XXX --cores 4`
Or edit shovill params in `assembly.smk`: `--ram 4G`

## Missing FASTQ Files

If `run_analysis.py` fails with MissingInputException:
1. Check samples.tsv paths: `cat workflows/bacmap/config/samples.tsv`
2. Verify FASTQ exists: `ls tests/fixtures/gold_standard/salmonella/data/SAM-XXX/`
3. Download from ENA: `python scripts/download_gold_standard.py`

## SISTR Returns N/A

If SISTR serotype is "N/A":
- Assembly may be too fragmented (check N50 > 10kb)
- Non-Salmonella species (check species_id.json verdict)
- SISTR binary may be missing: `which sistr`

## gmlst Hangs

gmlst requires Python 3.12+ in `.venv-gmlst`. If it hangs:
```bash
.venv-gmlst/bin/gmlst --version
```
If missing: `uv venv .venv-gmlst --python 3.12 && uv pip install --python .venv-gmlst/bin/python gmlst`

## abricate Database Missing

```
Error: database 'card' not found
```

Fix: The databases are pre-built in `data/reference/`. Rebuild:
```bash
makeblastdb -in data/reference/card_sequences.fasta -dbtype nucl -out data/reference/card
```

## SNP Pipeline Produces Empty Results

If SNP distance matrix is all zeros:
- Check that reference genome is chromosome-only: `grep -c "^>" data/reference/salmonella_LT2_ref.fasta` (should be 1)
- Verify BAM files have data: `samtools flagstat results/*/snp/snps.bam`
- Check joint VCF has variants: `bcftools view results/snp/joint.vcf.gz | grep -v "^#" | wc -l`

## Annotation Returns All Hypothetical

If annotation rate < 30%:
- Check Prokka DB BLAST indices exist: `ls data/reference/prokka_sprot.phr`
- Rebuild: `makeblastdb -in data/reference/prokka_sprot_abricate.fasta -dbtype prot -out data/reference/prokka_sprot`
- Check contigs aren't too short: annotation requires contigs ≥200bp
