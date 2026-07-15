# 快速安装

从零搭建 Hermes-bacmap 到跑通第一株分析。预计耗时 20–40 分钟。

前置条件见[环境准备](environment.md)：Linux x86_64、uv、pixi 已装好。

## 1. 克隆仓库

```bash
git clone https://github.com/indexofire/hermes-bacmap.git
cd hermes-bacmap
```

## 2. 生信工具环境（pixi）

```bash
pixi install
```

自动拉取全部生信 CLI + Python 3.12 运行时 + Python 依赖（biopython、pyrodigal、mappy、sourmash、gmlst 等）。

验证：

```bash
pixi run snakemake --version    # 7.32.x
pixi run shovill --version       # 1.1.0
pixi run abricate --version      # 1.4.0
pixi run iqtree --version        # 3.1.2
pixi run gmlst --version         # 0.1.0
```

## 3. 开发工具环境（uv，仅开发者需要）

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
```

验证：

```bash
uv run pytest -q
# → 184 passed
```

## 4. 构建数据库索引

参考数据库已随仓库分发在 `data/reference/`（按用途分类子目录），但 BLAST / bwa 索引需现场构建：

```bash
export PATH="$PWD/.pixi/envs/default/bin:$PATH"

# 核酸库
makeblastdb -in data/reference/species/markers.fasta   -dbtype nucl -out data/reference/species_markers
makeblastdb -in data/reference/amr/card.fasta          -dbtype nucl -out data/reference/card
makeblastdb -in data/reference/amr/vfdb.fasta          -dbtype nucl -out data/reference/vfdb
makeblastdb -in data/reference/plasmid/plasmidfinder.fasta -dbtype nucl -out data/reference/plasmidfinder
makeblastdb -in data/reference/serotype/ecoh.fasta     -dbtype nucl -out data/reference/ecoh
makeblastdb -in data/reference/serotype/shigella.fasta -dbtype nucl -out data/reference/shigella_ref
makeblastdb -in data/reference/virulence/vpara_targets.fasta -dbtype nucl -out data/reference/vpara_targets

# 蛋白库（Prokka 注释）
makeblastdb -in data/reference/annotation/prokka_sprot.fasta -dbtype prot -out data/reference/prokka_sprot
makeblastdb -in data/reference/annotation/prokka_is.fasta    -dbtype prot -out data/reference/prokka_is
makeblastdb -in data/reference/annotation/prokka_amr.fasta   -dbtype prot -out data/reference/prokka_amr

# SNP 参考基因组 bwa 索引
bwa index data/reference/genomes/salmonella_LT2.fasta
bwa index data/reference/genomes/ecoli_k12.fasta
bwa index data/reference/genomes/vpara_rimd.fasta
```

完整数据库清单见[参考数据库](../reference/databases.md)。

## 5. 下载验证数据集（可选）

10 株 ENA 公共数据用于验证管线：

```bash
pixi run python scripts/download_gold_standard.py
```

## 6. 安装插件到 Hermes Agent

```bash
# 安装到 Hermes 的 Python 环境（entry-point + 依赖自动注册）
pip install -e . --python ~/.hermes/hermes-agent/venv/bin/python

# 启用插件
hermes plugins enable hermes_bacmap
```

如果数据库不在仓库默认位置（如 pip install 到 site-packages 后），设置环境变量：

```bash
export BACMAP_DATA_DIR=/path/to/hermes-bacmap/data
```

## 7. 验证安装

### 7.1 跑测试

```bash
uv run pytest -q
# → 184 passed
```

| 文件 | 数量 | 覆盖 |
|---|---|---|
| `test_genome_object_service.py` | 50 | GOM schema / CRUD / 版本 / 文件 / 事件 / FTS5 |
| `test_strain_index.py` | 23 | 基因型溯源索引（search / find_similar / extract） |
| `test_deterministic_verifier.py` | 21 | 四类规则（正例 / 反例 / 边界） |
| `test_strain_metadata.py` | 24 | 元数据 + 实验室结果 + 三表 JOIN |
| `test_utils.py` | 15 | parse_mlst / parse_abricate / read_json_file |
| `test_engine.py` | 13 | merge_intervals / classify_allele / Hit.to_dict |
| `test_analysis.py` | 8 | species_identifier / failure_diagnostics / prokka_header |
| `test_cohort_ingest.py` | 9 | Cohort 创建 / 去重 / 树 / 距离 |
| `test_env.py` | 5 | 环境 + 工具链 |

### 7.2 检查引擎

```bash
pixi run python -c "
import sys; sys.path.insert(0, 'src')
from hermes_bacmap.engine import SequenceMatcher, ReadMapper, available
print('backends:', available())
"
# → backends: ['blastn', 'blastp', 'blastx', 'minimap2', 'tblastn']
```

### 7.3 跑通一株分析

```bash
pixi run python scripts/run_analysis.py --sample SAM-TYP-001
pixi run python scripts/ingest_results.py --sample SAM-TYP-001
pixi run python scripts/generate_report.py --sample SAM-TYP-001
```

预期结果：物种 = Salmonella，血清型 = Typhimurium，MLST ST19。详见[单株分析案例](../cases/single-sample.md)。

## 8. 启动 Hermes Agent

```bash
hermes chat
> 列出所有样本
> 分析 SAM-DEC-012
> 生成 SAM-TYP-001 的报告
```

如需切换到本地 LLM，见[本地 LLM 配置](local-llm.md)。

## 常见安装问题

| 问题 | 原因 | 解决 |
|---|---|---|
| `pixi install` 卡住 | 网络拉取 Conda 包 | 配置镜像：`pixi config set channel-alias https://mirrors.tuna.tsinghua.edu.cn/conda` |
| `makeblastdb: command not found` | pixi 环境未进 PATH | `pixi shell` 或 `export PATH="$PWD/.pixi/envs/default/bin:$PATH"` |
| `hermes: command not found` | Hermes Agent 未装 | 见 [Hermes 安装文档](https://hermes-agent.nousresearch.com/docs/getting-started/installation) |
| `database 'card' not found` | BLAST 索引未建 | 重跑第 4 步 |
| `ModuleNotFoundError: hermes_bacmap` | 插件未安装到 Hermes venv | 重跑第 6 步 `pip install -e .` |

更多错误见[故障排查](../reference/troubleshooting.md)。
