# 工具列表

Hermes-bacmap 注册 **18 个 Tools**，分为两类：8 个生信原语（底层算法封装）与 10 个高层分析工具（业务级流程）。所有 tool 在 `src/hermes_bacmap/tools.py` 实现 handler，`schemas.py` 定义 JSON Schema。

## 生信原语（8 个）

通用序列与比对操作，不绑定具体病原。

| Tool | 功能 | 输入 | 输出 | 底层工具 |
|---|---|---|---|---|
| `bio_seq_stats` | FASTA / FASTQ / GenBank 统计 | 序列文件路径 | N50、GC、长度分布、质量分布 | Biopython |
| `bio_seq_ops` | 序列操作 | 序列文件 | 反向互补、翻译、GC-skew、motif、ORF、限制位点、k-mer | Biopython |
| `bio_fastq_qc` | FASTQ 质控 + adapter 检测 | FASTQ 文件 | 质控 JSON（before/after filtering） | fastp |
| `bio_seq_convert` | 格式转换 | 序列文件 | FASTA / FASTQ / GenBank / EMBL 等 9 种互转 | Biopython |
| `bio_blast` | 本地 + 远程（NCBI）BLAST | query + db | Hit 列表（identity / coverage / evalue） | blastn / blastp / blastx |
| `bio_align` | 序列比对 | reads + reference | sorted BAM（含索引） | BWA-MEM / minimap2 / STAR |
| `bio_samtools` | SAM / BAM 操作 | BAM 文件 | index / sort / flagstat / view / depth / faidx / mpileup / consensus / fixmate | samtools（9 子命令） |
| `bio_variant` | 变异检测 | BAM / VCF | mpileup_call / filter / query / annotate / consensus | bcftools |

底层比对通过 [Engine 引擎层](../architecture/engine.md) 的 `SequenceMatcher` / `ReadMapper` 统一调度，自动选 blastn / blastp / minimap2 / bwa 后端。

## 高层分析工具（10 个）

病原特异性业务流程，封装为单次调用。

| Tool | 功能 | 输入 | 输出 |
|---|---|---|---|
| `bio_analyze_salmonella` | 触发 Snakemake 全流程（跨病原自动路由） | `sample_id` | `{sample}_summary.json` |
| `bio_get_result` | 获取单株紧凑结果摘要 | `sample_id` | JSON（species / mlst / serotype / amr） |
| `bio_verify_result` | 运行 Deterministic Verifier | `sample_id` | VerificationResult（passed / checks / needs_review） |
| `bio_generate_report` | 生成 HTML 报告（单株 / 全量 / cohort） | `sample_id` 或 `--cohort` | HTML 文件 |
| `bio_list_samples` | 列出所有样本及分析状态 | 无 | 样本状态列表 |
| `bio_gene_scan` | 多数据库基因扫描 | `contigs` + `database` | 基因列表（identity / coverage） |
| `bio_snp_tree` | 获取 cohort 系统发育树 + 距离矩阵 | 无 | Newick + pairwise distances |
| `bio_search_samples` | 自然语言样本检索 | `query` | 匹配样本（含匹配字段 + 相关度分数） |
| `bio_annotate` | 基因组注释 | `contigs_path` | annotation JSON（CDS + 功能） |
| `bio_diagnose` | 诊断管线失败 | `log_path` 或 `stderr_text` | 错误类型 / 根因 / 影响规则 / 修复命令 |

## bio_gene_scan 支持的数据库

`bio_gene_scan` 运行时动态扫描，支持 9 种数据库：

```
card, vfdb, ecoh, plasmidfinder, resfinder, ncbi, megares, victors, ecoli_vf
```

底层由 `gene_scanner.py`（420 行）驱动，委托 [engine.SequenceMatcher](../architecture/engine.md)。检查 BLAST 返回码，非零 raise（防止静默假阴性）。

## bio_search_samples 加权策略

自然语言检索使用字段加权，分数高者排名靠前：

| 匹配字段 | 分数 | 示例 |
|---|---|---|
| serotype 精确匹配 | 10 | 搜 "Typhimurium" → sistr=Typhimurium |
| MLST ST 匹配 | 10 | 搜 "ST2" → mlst_st=2 |
| AMR 基因名匹配 | 9 | 搜 "CRP" → amr genes 含 CRP |
| MLST 原始文本 | 8 | TSV 中任意字段匹配 |
| plasmid 匹配 | 7 | PlasmidFinder 基因名 |
| strain_id 匹配 | 6 | 样本编号 |
| organism 匹配 | 5 | 物种名 |
| FTS5 全文匹配 | 1 | 降级兜底 |

搜索流程：遍历 ANALYSIS 对象（排除 `cohort:` 前缀）→ 计算各字段匹配分 → 去重（多版本取最新）→ 按 score 降序返回前 50 条。

## bio_diagnose 错误类型

`bio_diagnose` 解析 Snakemake 日志，识别以下错误类别并给出修复命令：

| 错误类别 | 触发信号 | 典型修复 |
|---|---|---|
| OutOfMemory | `signal 9 (SIGKILL)` | 降低 `--cores` 或 Shovill `--ram` |
| LockConflict | `Directory cannot be locked` | `snakemake --unlock` |
| MissingTool | `command not found` | `pixi install` |
| MissingDatabase | `database 'X' not found` | `makeblastdb` 重建索引 |
| MissingInput | `MissingInputException` | 检查 samples.tsv、下载数据 |
| DiskFull | `No space left on device` | 清理结果目录 |
| VersionMismatch | Snakemake 版本错误 | 锁定 7.32.x |

## bio_verify_result 校验类别

Deterministic Verifier 对单株结果执行四类校验（21 个 TDD 测试覆盖）：

| 检查类别 | 规则 | 失败处理 |
|---|---|---|
| Species | `species_verdict` 包含 "Salmonella" | FAIL |
| MLST | `mlst` 字段非空且有 ST 数字 | WARN |
| Serotype | `serotype.sistr` 非空 | WARN |
| AMR | 关键基因（CTX-M/NDM/KPC/mcr-1）触发审核 | NEEDS_REVIEW |

代码接口：

```python
from hermes_bacmap.deterministic_verifier import DeterministicVerifier

v = DeterministicVerifier()
result = v.verify_all(summary_dict)
# result.passed              → bool
# result.checks              → list[CheckResult]
# result.needs_human_review  → bool
# result.failed_count        → int
```

## 调用方式

Tools 通过 Hermes Agent 自然语言触发，也可在 Python 中直接调用 handler：

```python
from hermes_bacmap.tools import list_samples, get_result, search_samples

# 列出样本
print(list_samples({}))

# 获取结果
print(get_result({"sample_id": "SAM-TYP-001"}))

# 检索
print(search_samples({"query": "Typhimurium"}))
```

Web UI 的 `/api/search` 端点也直接调用 `search_samples` handler。

## 相关

- [Engine 引擎层](../architecture/engine.md) — 底层算法封装
- [Snakemake 管线](../architecture/pipeline.md) — `bio_analyze_salmonella` 触发的 22 条规则
- [参考数据库](databases.md) — `bio_blast` / `bio_gene_scan` 依赖的 13 个 FASTA 库
- [故障排查](troubleshooting.md) — `bio_diagnose` 识别的错误详解
