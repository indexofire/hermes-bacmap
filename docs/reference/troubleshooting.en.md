# Troubleshooting

This page summarizes common errors and fixes for the hermes-bacmap analysis pipeline. For the full version, see `skills/run-pipeline/references/troubleshooting.md`.

## Automatic Diagnosis

Prefer submitting the error message or sample ID to the Hermes `bio_diagnose` tool; the system automatically matches error patterns and suggests fixes.

```
> bio_diagnose sample=SAM-XXX error="snakemake lock"
```

## Common Error Reference

| Symptom | Root cause | Fix |
|---|---|---|
| `Directory cannot be locked` | Snakemake lock not released | `cd workflows/bacmap && snakemake --unlock` |
| `signal 9 (SIGKILL)` | Shovill / SPAdes OOM | `--cores 4` or change to `--ram 4G` |
| `MissingInputException` | Wrong FASTQ path or missing file | Check `samples.tsv`; run `download_gold_standard.py` if needed |
| `database 'card' not found` | BLAST DB index missing | `makeblastdb -in amr/card.fasta -dbtype nucl -out card` |
| SISTR outputs `N/A` | Fragmented assembly or not Salmonella | Check N50 >10 kb and `species_id.json`; verify with `which sistr` |
| gmlst hangs/errors | Not using Python 3.12 | `uv venv pixi (gmlst now included) --python 3.12 && uv pip install --python pixi (gmlst now included)/bin/python gmlst` |
| SNP matrix is all zeros | Reference genome has multiple sequences, or BAM has no data | Confirm the reference has only 1 chromosome; check `samtools flagstat` and the VCF variant count |
| Annotation rate <30% | Prokka DB index missing, or contigs too short | Check `prokka_sprot.phr`; rebuild with `-dbtype prot`; contigs ≥200 bp |

## Snakemake Lock

```
Error: Directory cannot be locked. Please make sure that nothing else uses the directory.
```

Fix:

```bash
cd workflows/bacmap
snakemake --unlock
```

## Shovill OOM

Shovill assembly can peak at 8–16 GB. When `SIGKILL` occurs on low-spec machines:

```bash
python scripts/run_analysis.py --sample SAM-XXX --cores 4
```

Or edit `workflows/bacmap/rules/assembly.smk` to limit `--ram` to 4G.

## gmlst Environment

gmlst requires Python 3.12+. Verify:

```bash
pixi run gmlst --version
```

If missing:

```bash
uv venv pixi (gmlst now included) --python 3.12
uv pip install --python pixi (gmlst now included)/bin/python gmlst
```

## Missing Databases

```
Error: database 'card' not found
```

Fix examples:

```bash
makeblastdb -in data/reference/amr/card.fasta -dbtype nucl -out data/reference/card
makeblastdb -in data/reference/amr/vfdb.fasta -dbtype nucl -out data/reference/vfdb
makeblastdb -in data/reference/plasmid/plasmidfinder.fasta -dbtype nucl -out data/reference/plasmidfinder
makeblastdb -in data/reference/species/markers.fasta -dbtype nucl -out data/reference/species_markers
```

## Investigating Empty SNP Results

1. The reference genome must be chromosome-only:
   ```bash
   grep -c "^>" data/reference/genomes/salmonella_LT2.fasta   # 应为 1
   ```
2. Check the BAM:
   ```bash
   samtools flagstat results/SAM-XXX/snp/snps.bam
   ```
3. Check the VCF variant count:
   ```bash
   bcftools view results/snp/joint.vcf.gz | grep -v "^#" | wc -l
   ```

## Still Stuck?

1. Check the status: `python scripts/run_analysis.py --status`
2. Check the latest Snakemake log: `ls -t workflows/bacmap/.snakemake/logs/*.snakemake.log | head -1 | xargs tail -80`
3. Submit the full log via `bio_diagnose`
