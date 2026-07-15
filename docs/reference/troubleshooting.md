# 故障排查 Troubleshooting

本页汇总 hermes-bacmap 分析管线常见错误与修复。完整版本见 `skills/run-pipeline/references/troubleshooting.md`。

## 自动诊断

优先使用 Hermes `bio_diagnose` tool 提交错误信息或样本 ID，系统自动匹配错误模式并给出修复建议。

```
> bio_diagnose sample=SAM-XXX error="snakemake lock"
```

## 常见错误对照表

| 错误现象 | 根因 | 修复方法 |
|---|---|---|
| `Directory cannot be locked` | Snakemake 锁未释放 | `cd workflows/salmonella && snakemake --unlock` |
| `signal 9 (SIGKILL)` | Shovill / SPAdes OOM | `--cores 4` 或改 `--ram 4G` |
| `MissingInputException` | FASTQ 路径错误或文件缺失 | 检查 `samples.tsv`；必要时 `download_gold_standard.py` |
| `database 'card' not found` | BLAST DB 索引缺失 | `makeblastdb -in amr/card.fasta -dbtype nucl -out card` |
| SISTR 输出 `N/A` | 组装碎片化或非 Salmonella | 检查 N50 >10kb 与 `species_id.json`；确认 `which sistr` |
| gmlst 挂起/报错 | 未使用 Python 3.12 | `uv venv pixi (gmlst now included) --python 3.12 && uv pip install --python pixi (gmlst now included)/bin/python gmlst` |
| SNP 矩阵全 0 | 参考基因组含多条序列或 BAM 无数据 | 确认参考仅 1 条 chromosome；检查 `samtools flagstat` 与 VCF 变异数 |
| 注释率 <30% | Prokka DB 索引缺失或 contigs 过短 | 检查 `prokka_sprot.phr`；重建 `-dbtype prot`；contigs ≥200bp |

## Snakemake Lock

```
Error: Directory cannot be locked. Please make sure that nothing else uses the directory.
```

修复：

```bash
cd workflows/salmonella
snakemake --unlock
```

## Shovill OOM

Shovill 组装峰值可达 8–16 GB。低配机器出现 `SIGKILL` 时：

```bash
python scripts/run_analysis.py --sample SAM-XXX --cores 4
```

或编辑 `workflows/salmonella/rules/assembly.smk`，将 `--ram` 限制为 4G。

## gmlst 环境

gmlst 需要 Python 3.12+。验证：

```bash
pixi run gmlst --version
```

若缺失：

```bash
uv venv pixi (gmlst now included) --python 3.12
uv pip install --python pixi (gmlst now included)/bin/python gmlst
```

## 数据库缺失

```
Error: database 'card' not found
```

修复示例：

```bash
makeblastdb -in data/reference/amr/card.fasta -dbtype nucl -out data/reference/card
makeblastdb -in data/reference/amr/vfdb.fasta -dbtype nucl -out data/reference/vfdb
makeblastdb -in data/reference/plasmid/plasmidfinder.fasta -dbtype nucl -out data/reference/plasmidfinder
makeblastdb -in data/reference/species/markers.fasta -dbtype nucl -out data/reference/species_markers
```

## SNP 空结果排查

1. 参考基因组必须 chromosome-only：
   ```bash
   grep -c "^>" data/reference/genomes/salmonella_LT2.fasta   # 应为 1
   ```
2. 检查 BAM：
   ```bash
   samtools flagstat results/SAM-XXX/snp/snps.bam
   ```
3. 检查 VCF 变异数：
   ```bash
   bcftools view results/snp/joint.vcf.gz | grep -v "^#" | wc -l
   ```

## 仍无法解决？

1. 查看状态：`python scripts/run_analysis.py --status`
2. 查看 Snakemake 最新日志：`ls -t workflows/salmonella/.snakemake/logs/*.snakemake.log | head -1 | xargs tail -80`
3. 通过 `bio_diagnose` 提交完整日志

