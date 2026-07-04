# 快速安装

从零搭建 Hermes-bacmap 到跑通第一株分析。预计耗时 30–60 分钟（含数据库下载）。

前置条件见[环境准备](environment.md)：Linux x86_64、uv、pixi 已装好。

## 1. 克隆仓库

```bash
git clone https://github.com/indexofire/hermes-bacmap.git
cd hermes-bacmap
```

## 2. Python 主环境

```bash
# 创建 Python 3.11 虚拟环境
uv venv --python 3.11

# 安装项目（含开发依赖）
uv pip install -e ".[dev]"
```

验证：

```bash
uv run python -c "import hermes_bacmap; print('plugin loaded')"
# → plugin loaded
```

## 3. 生信工具环境

```bash
# 解析 pixi.toml 并安装全部生信 CLI 到 .pixi/
pixi install
```

验证：

```bash
pixi run snakemake --version    # 7.32.x
pixi run shovill --version       # 1.1.0
pixi run abricate --version      # 1.4.0
pixi run iqtree --version        # 3.1.2
```

## 4. gmlst 独立环境

gmlst 上游要求 Python ≥ 3.12，与主环境（3.11）隔离：

```bash
uv venv .venv-gmlst --python 3.12
uv pip install --python .venv-gmlst/bin/python gmlst
```

验证：

```bash
.venv-gmlst/bin/gmlst --version
# → gmlst 0.1.0
```

## 5. 下载参考数据库

参考数据库随仓库分发在 `data/reference/`，但部分 BLAST 索引需现场构建。检查并补建：

```bash
# 检查 AMR / 毒力 / 质粒数据库索引
ls data/reference/*.nhr 2>/dev/null | head

# 若缺失，重建索引（nucl 库）
makeblastdb -in data/reference/card_sequences.fasta \
    -dbtype nucl -out data/reference/card
makeblastdb -in data/reference/vfdb_sequences.fasta \
    -dbtype nucl -out data/reference/vfdb
makeblastdb -in data/reference/plasmidfinder_sequences.fasta \
    -dbtype nucl -out data/reference/plasmidfinder
makeblastdb -in data/reference/species_markers.fasta \
    -dbtype nucl -out data/reference/species_markers
```

Prokka 蛋白库（注释用，蛋白库）：

```bash
makeblastdb -in data/reference/prokka_sprot_abricate.fasta \
    -dbtype prot -out data/reference/prokka_sprot
```

完整数据库清单见[参考数据库](../reference/databases.md)。

## 6. 下载 Gold Standard 验证数据集

10 株 ENA 公共数据用于验证管线：

```bash
# 多线程下载（aria2c）+ MD5 校验
python scripts/download_gold_standard.py

# 验证文件存在
ls tests/fixtures/gold_standard/salmonella/data/SAM-TYP-001/
# → SAM-TYP-001_R1.fastq.gz  SAM-TYP-001_R2.fastq.gz
```

## 7. 部署到 Hermes Agent

将插件链接到 Hermes venv：

```bash
# 1. 安装运行时依赖到 Hermes venv
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python biopython pydantic

# 2. 软链接插件目录
ln -sf "$(pwd)/src/hermes_bacmap" ~/.hermes/plugins/hermes_bacmap

# 3. 启用插件
hermes plugins enable hermes_bacmap
```

## 8. 验证安装

### 8.1 跑测试

```bash
uv run pytest -q
# → 96 passed in XX.XXs
```

测试分四组：

| 文件 | 数量 | 覆盖 |
|---|---|---|
| `test_genome_object_service.py` | 50 | GOM schema / CRUD / 版本 / 文件 / 事件 |
| `test_deterministic_verifier.py` | 21 | 四类规则（正例 / 反例 / 边界） |
| `test_cohort_ingest.py` | 9 | Cohort 创建 / 去重 / 树 / 距离 |
| `test_env.py` | 5 | 环境 + 工具链 |

### 8.2 检查关键工具

```bash
uv run python -c "
from hermes_bacmap.engine import SequenceMatcher, ReadMapper, available
print('engine backends:', available())
"
# → engine backends: ['blastn', 'blastp', 'blastx', 'minimap2', 'tblastn']
```

### 8.3 跑通一株分析

```bash
# 端到端分析 SAM-TYP-001（S. Typhimurium）
python scripts/run_analysis.py --sample SAM-TYP-001

# 查看状态
python scripts/run_analysis.py --status

# 入库到 GOM
python scripts/ingest_results.py --sample SAM-TYP-001

# 生成 HTML 报告
python scripts/generate_report.py --sample SAM-TYP-001
```

预期结果：物种 = Salmonella，血清型 = Typhimurium，MLST ST19。详见[单株分析案例](../cases/single-sample.md)。

## 9. 启动 Hermes Agent

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
| `gmlst: command not found` | 未激活 .venv-gmlst | 使用绝对路径 `.venv-gmlst/bin/gmlst` |
| `makeblastdb: command not found` | pixi 环境未进 PATH | `pixi shell` 进入 shell，或 `pixi run makeblastdb` |
| `hermes: command not found` | Hermes Agent 未装 | 见 [Hermes Agent 安装文档](https://github.com/NousResearch/hermes-agent) |
| `database 'card' not found` | BLAST 索引未建 | 重跑第 5 步 `makeblastdb` |

更多错误见[故障排查](../reference/troubleshooting.md)。
