# 命令行工具

Hermes-bacmap 提供四个编排脚本，覆盖**运行分析 → 结果入库 → 生成报告 → 切换 LLM** 全流程。所有脚本位于 `scripts/` 目录，需在项目根目录执行。

```bash
# 所有命令均在项目根目录执行
cd ~/repo/github/hermes-bacmap
```

## run_analysis.py — 端到端分析编排器

触发 Snakemake DAG，自动完成 QC → 组装 → 物种鉴定 → MLST → 血清型 → AMR → 注释 → 汇总。物种路由全自动：invA 阳性走 Salmonella 管线，uidA 阳性走 DEC 管线，以此类推。

```text
usage: run_analysis.py [-h] (--sample SAMPLE | --all | --snp | --status) [--cores CORES]

options:
  --sample SAMPLE  分析单个样本（如 SAM-TYP-001）
  --all            批量分析 samples.tsv 中所有样本
  --snp            运行 cohort 级 SNP 系统发育分析
  --status         查看所有样本分析进度
  --cores CORES    Snakemake 并行核数（默认 8）
```

### 单样本分析

```bash
python scripts/run_analysis.py --sample SAM-TYP-001
```

输出分布：

```
results/SAM-TYP-001/
├── qc/SAM-TYP-001_fastp.json          质控报告
├── assembly/contigs.fasta              组装结果
├── assembly/assembly_stats.tsv         组装统计
├── species/species_id.json             物种鉴定
├── typing/mlst.tsv                     MLST
├── typing/sistr.json                   血清型（Salmonella）
├── amr/abricate_{card,vfdb,plasmidfinder}.tsv   AMR / 毒力 / 质粒
├── annotation/annotation.json          基因组注释
└── report/SAM-TYP-001_summary.json     汇总
```

### 批量分析

```bash
# 分析 samples.tsv 中全部样本（10 株 Gold Standard）
python scripts/run_analysis.py --all

# 限制 4 核（低配机器）
python scripts/run_analysis.py --all --cores 4
```

`--all` 会检测已完成样本并跳过；缺失 summary 的样本会在结束时统计并以 exit 1 提示。

### 查看状态

```bash
python scripts/run_analysis.py --status
```

输出示例：

```
分析状态：
  SAM-TYP-001    completed   Salmonella Typhimurium ST19
  SAM-DEC-012    completed   E. coli O153:H2
  SAM-SHI-013    in-progress (assembly done)
  SAM-EIEC-014   not-started

完成 8/10 · SNP cohort: ready
```

### SNP cohort 分析

```bash
# 需 ≥2 株同物种样本已完成单株分析
python scripts/run_analysis.py --snp
```

触发 5 步 SNP 管线：每株 BWA 比对 → 联合变异检测 → 全基因组 SNP 矩阵 → IQ-TREE 建树 → 距离矩阵汇总。详见[Snakemake 管线](../architecture/pipeline.md)。

### 关键特性

- **样本验证**：未知 sample_id 报错并列出有效样本
- **超时保护**：subprocess 超时 7200s，防止无限挂起
- **失败诊断**：失败时输出 3 步诊断建议（检查日志 → 解锁 → 重试）

## ingest_results.py — GOM 入库

将 Snakemake 结果写入 Genome Object Model (SQLite)。自动版本管理、去重、SHA256 校验。

```text
usage: ingest_results.py [-h] (--sample SAMPLE | --all | --snp)
```

```bash
# 单株入库
python scripts/ingest_results.py --sample SAM-TYP-001

# 全量入库（先于 SNP）
python scripts/ingest_results.py --all

# SNP cohort 入库（在 --all 之后执行）
python scripts/ingest_results.py --snp
```

入库逻辑：

| strain_id 状态 | pipeline_version 相同 | 行为 |
|---|---|---|
| 不存在 | — | 创建 v1 |
| 已存在 | 是 | 跳过（`⏭️ 已存在 v1, skipped`） |
| 已存在 | 否 | 创建新版本 v+1（Immutable + Version First） |

每株入库会创建：1 个 ANALYSIS 对象 + 9 个文件产物 + 5 个生命周期事件。详见[GOM 数据模型](../architecture/gom.md)。

## generate_report.py — HTML 报告

生成可视化 HTML 报告，整合物种、MLST、血清型、AMR、注释、SNP 距离矩阵。

```text
usage: generate_report.py [-h] (--sample SAMPLE | --all | --cohort)
```

```bash
# 单株报告
python scripts/generate_report.py --sample SAM-TYP-001
# → results/SAM-TYP-001/report/SAM-TYP-001_report.html

# 全量报告
python scripts/generate_report.py --all

# Cohort SNP 报告（系统发育树 + 距离矩阵）
python scripts/generate_report.py --cohort
# → results/snp/cohort_report.html
```

## switch_llm.py — LLM Provider 切换

切换 Hermes Agent 的推理后端（云端 / 本地）。详见[本地 LLM 配置](../installation/local-llm.md)。

```text
usage: switch_llm.py [-h] {zai,ollama,vllm,llamacpp,status}
```

```bash
# 查看当前 provider
python scripts/switch_llm.py status

# 切到 Ollama（需先 ollama serve &）
python scripts/switch_llm.py ollama

# 切回云端 Z.AI（GLM-5.2）
python scripts/switch_llm.py zai

# 切换后重启 Hermes
hermes chat
```

## 辅助脚本

| 脚本 | 用途 |
|---|---|
| `download_gold_standard.py` | 从 ENA 下载 10 株验证数据集（aria2c + MD5 校验） |
| `generate_snp_matrix.py` | VCF → FASTA SNP 矩阵（whole-genome mode） |
| `collect_summary.py` | Snakemake 脚本：聚合各步骤为 summary.json |
| `generate_snp_summary.py` | treefile + FASTA → snp_summary.json |
| `call_pathotype.py` | DEC pathotype 判定（stx1/stx2/eae/ipaH/...） |

## 典型工作流

```bash
# 1. 批量分析
python scripts/run_analysis.py --all

# 2. SNP cohort（可选，需同物种 ≥2 株）
python scripts/run_analysis.py --snp

# 3. 入库（先单株后 SNP）
python scripts/ingest_results.py --all
python scripts/ingest_results.py --snp

# 4. 报告
python scripts/generate_report.py --all
python scripts/generate_report.py --cohort
```

!!! tip "断点续跑"
    Snakemake 状态持久化在 `.snakemake/`。会话中断后重连，先 `run_analysis.py --status` 查看进度，再 `run_analysis.py --sample SAM-XXX` 续跑。若目录被锁，见[故障排查](../reference/troubleshooting.md)。

命令行之外，也可通过 [Hermes Agent](hermes-agent.md) 自然语言交互，或用 [Web UI](web-ui.md) 浏览结果。
