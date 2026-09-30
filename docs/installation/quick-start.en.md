# Quick Installation

Set up Hermes-bacmap from scratch and run your first isolate analysis. Estimated time: 20–40 minutes.

Prerequisites are covered in [Environment Setup](environment.md): Linux x86_64, uv, and pixi installed.

## 1. Clone the Repository

```bash
git clone https://github.com/indexofire/hermes-bacmap.git
cd hermes-bacmap
```

## 2. Bioinformatics Tool Environment (pixi)

```bash
pixi install
```

This automatically pulls all bioinformatics CLIs + the Python 3.12 runtime + Python dependencies (biopython, pyrodigal, mappy, sourmash, gmlst, etc.).

Verify:

```bash
pixi run snakemake --version    # 7.32.x
pixi run shovill --version       # 1.1.0
pixi run abricate --version      # 1.4.0
pixi run iqtree --version        # 3.1.2
pixi run gmlst --version         # 0.1.0
```

## 3. Dev Tool Environment (uv, developers only)

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
```

Verify:

```bash
uv run pytest -q
# → 184 passed
```

## 4. Build Database Indexes

Reference databases ship with the repository in `data/reference/` (subdirectories organized by purpose), but BLAST / bwa indexes must be built on site:

```bash
export PATH="$PWD/.pixi/envs/default/bin:$PATH"

# 核酸库
makeblastdb -in data/reference/species/markers.fasta   -dbtype nucl -out data/reference/species_markers
makeblastdb -in data/reference/amr/card.fasta          -dbtype nucl -out data/reference/card
makeblastdb -in data/reference/amr/vfdb.fasta          -dbtype nucl -out data/reference/vfdb
makeblastdb -in data/reference/plasmid/plasmidfinder.fasta -dbtype nucl -out data/reference/plasmidfinder
makeblastdb -in data/reference/serotype/ecoh.fasta     -dbtype nucl -out data/reference/ecoh
makeblastdb -in data/reference/serotype/shigella.fasta -dbtype nucl -out data/reference/shigella_ref
makeblastdb -in data/reference/virulence/virulence/vpara_targets.fasta -dbtype nucl -out data/reference/vpara_targets

# 蛋白库（Prokka 注释）
makeblastdb -in data/reference/annotation/prokka_sprot.fasta -dbtype prot -out data/reference/prokka_sprot
makeblastdb -in data/reference/annotation/prokka_is.fasta    -dbtype prot -out data/reference/prokka_is
makeblastdb -in data/reference/annotation/prokka_amr.fasta   -dbtype prot -out data/reference/prokka_amr

# SNP 参考基因组 bwa 索引
bwa index data/reference/genomes/salmonella_LT2.fasta
bwa index data/reference/genomes/ecoli_k12.fasta
bwa index data/reference/genomes/vpara_rimd.fasta
```

For the full database inventory, see [Reference Databases](../reference/databases.md).

## 5. Download the Validation Dataset (optional)

Ten ENA public isolates are used to validate the pipeline:

```bash
pixi run python scripts/download_gold_standard.py
```

## 6. Install the Plugin into Hermes Agent

```bash
# 安装到 Hermes 的 Python 环境（entry-point + 依赖自动注册）
pip install -e . --python ~/.hermes/hermes-agent/venv/bin/python

# 启用插件
hermes plugins enable hermes_bacmap
```

If the databases are not at the repository default location (e.g., after a pip install into site-packages), set the environment variable:

```bash
export BACMAP_DATA_DIR=/path/to/hermes-bacmap/data
```

If you use the standard species identification mode (CheckM2 + GTDB-Tk), also set:

```bash
export CHECKM2DB=/data/databases/checkm2_db
export GTDBDB=/data/databases/gtdb_r220
```

And switch the mode in `workflows/bacmap/config/config.yaml`:

```yaml
species_mode: standard   # simple（默认）或 standard
```

## 7. Verify the Installation

### 7.1 Run the tests

```bash
uv run pytest -q
# → 184 passed
```

| File | Count | Coverage |
|---|---|---|
| `test_genome_object_service.py` | 50 | GOM schema / CRUD / versioning / files / events / FTS5 |
| `test_strain_index.py` | 23 | Genotype trace-back index (search / find_similar / extract) |
| `test_deterministic_verifier.py` | 21 | Four rule categories (positive / negative / boundary cases) |
| `test_strain_metadata.py` | 24 | Metadata + lab results + three-table JOIN |
| `test_utils.py` | 15 | parse_mlst / parse_abricate / read_json_file |
| `test_engine.py` | 13 | merge_intervals / classify_allele / Hit.to_dict |
| `test_analysis.py` | 8 | species_identifier / failure_diagnostics / prokka_header |
| `test_cohort_ingest.py` | 9 | Cohort creation / deduplication / tree / distances |
| `test_env.py` | 5 | Environment + toolchain |

### 7.2 Check the engine

```bash
pixi run python -c "
import sys; sys.path.insert(0, 'src')
from hermes_bacmap.engine import SequenceMatcher, ReadMapper, available
print('backends:', available())
"
# → backends: ['blastn', 'blastp', 'blastx', 'minimap2', 'tblastn']
```

### 7.3 Run one isolate end to end

```bash
pixi run python scripts/run_analysis.py --sample SAM-TYP-001
pixi run python scripts/ingest_results.py --sample SAM-TYP-001
pixi run python scripts/generate_report.py --sample SAM-TYP-001
```

Expected results: species = Salmonella, serotype = Typhimurium, MLST ST19. See the [single-isolate case study](../cases/single-sample.md).

## 8. Start the Hermes Agent

```bash
hermes chat
> 列出所有样本
> 分析 SAM-DEC-012
> 生成 SAM-TYP-001 的报告
```

To switch to a local LLM, see [Local LLM Configuration](local-llm.md).

## Common Installation Issues

| Problem | Cause | Fix |
|---|---|---|
| `pixi install` hangs | Network is slow pulling Conda packages | Configure a mirror: `pixi config set channel-alias https://mirrors.tuna.tsinghua.edu.cn/conda` |
| `makeblastdb: command not found` | pixi environment not on PATH | `pixi shell` or `export PATH="$PWD/.pixi/envs/default/bin:$PATH"` |
| `hermes: command not found` | Hermes Agent not installed | See the [Hermes installation docs](https://hermes-agent.nousresearch.com/docs/getting-started/installation) |
| `database 'card' not found` | BLAST indexes not built | Re-run step 4 |
| `ModuleNotFoundError: hermes_bacmap` | Plugin not installed into the Hermes venv | Re-run step 6 `pip install -e .` |

For more errors, see [Troubleshooting](../reference/troubleshooting.md).


## (Optional) GBrain knowledge base

Enable the knowledge layer (finding capture + semantic retrieval +
pre-registration checks), see
[GBrain knowledge base setup](gbrain.en.md):

```bash
bash scripts/setup_gbrain.sh
```

Without it the knowledge tools degrade gracefully; core analysis is unaffected.
