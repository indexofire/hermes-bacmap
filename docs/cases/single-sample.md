# 单株分析案例

本案例演示从 FASTQ 到报告的完整流程，分析 **SAM-TYP-001**（S. Typhimurium 标准株，来自 ENA Gold Standard 数据集）。

## 场景

某疾控实验室收到一株疑似沙门菌分离株，Illumina PE150 测序已完成。需求：

- 确认物种（是否为 Salmonella）
- 确定血清型与 MLST 型
- 检测耐药基因与毒力因子
- 生成可归档的 HTML 报告

预期耗时：约 40–60 分钟（8 核 / 32 GB RAM 推荐档硬件）。

## Step 1 · 查看状态

先确认样本已在样本表中、且尚未分析：

```bash
python scripts/run_analysis.py --status
```

输出：

```
分析状态：
  SAM-TYP-001    not-started
  SAM-TYP-002    not-started
  ...
完成 0/10 · SNP cohort: not-ready
```

或通过 Hermes Agent：

```
> 列出所有样本
```

## Step 2 · 端到端分析

```bash
python scripts/run_analysis.py --sample SAM-TYP-001
```

或 Hermes Agent：

```
> 分析 SAM-TYP-001
```

Agent 调用 `bio_analyze_salmonella`，触发 Snakemake DAG。每步进度实时输出：

```
启动分析 SAM-TYP-001 ...
✓ QC (fastp)                     1-2 min
✓ Assembly (Shovill, N50=215kb)  30-50 min
✓ Species identify               <1 min
✓ MLST (gmlst salmonella_2)      1-2 min
✓ Serotype (SISTR)               <1 min
✓ AMR (abricate ×3)              2-3 min
✓ Annotation (pyrodigal+blastp)  2-3 min
报告汇总已生成
```

物种路由全自动：`species_identify` 规则用一次 BLAST 检测 invA / uidA / ipaH / toxR / tlh 五基因，命中 invA 即走 Salmonella 分支（typing_mlst + typing_sistr），其余规则被 DAG 剪枝。

## Step 3 · 查看结果

```bash
# 紧凑结果摘要（JSON）
cat results/SAM-TYP-001/report/SAM-TYP-001_summary.json | python -m json.tool
```

或 Hermes Agent：

```
> SAM-TYP-001 的结果
```

调用 `bio_get_result`，返回核心字段：

```json
{
  "strain_id": "SAM-TYP-001",
  "species_verdict": "Salmonella",
  "serotype": {
    "sistr": "Typhimurium",
    "serogroup": "B",
    "o_antigen": "1,4,[5],12",
    "h1": "i",
    "h2": "1,2"
  },
  "mlst": "SAM-TYP-001\tsalmonella_2\tST19\taroC\tdnaN\themD\t...19",
  "amr": {
    "abricate_card": [
      {"GENE": "blaTEM-1", "%IDENTITY": 99.8, "%COVERAGE": 100.0}
    ],
    "abricate_vfdb": [
      {"GENE": "spiA", "%IDENTITY": 98.5}
    ]
  }
}
```

## Step 4 · 预期结果

| 分析项 | 预期结果 | 说明 |
|---|---|---|
| **物种** | Salmonella（invA 阳性） | M90846.1 参考命中，identity ≥90%, coverage ≥80% |
| **血清型** | **Typhimurium**（serogroup B） | SISTR 输出，O:1,4,[5],12 / H:i / H:1,2 |
| **MLST** | **ST19**（salmonella_2 scheme） | aroC/dnaN/hemD/hisD/pureG/sepA/stra 七基因型 |
| **AMR** | blaTEM-1（青霉素酶） | abricate CARD 库检出 |
| **毒力** | spiA 等沙门菌特异毒力因子 | abricate VFDB 库检出 |
| **组装 N50** | ~215 kb | 满足 >100 kb 的 Good 阈值 |
| **注释率** | ~72% | pyrodigal CDS + Prokka DB blastp |

## Step 5 · 入库 GOM

将结果写入 SQLite，建立可追溯、版本化记录：

```bash
python scripts/ingest_results.py --sample SAM-TYP-001
```

入库会创建：

- 1 个 `ANALYSIS` GenomeObject（v1，payload 含全部结果）
- 9 个 `file_artifacts`（assembly / qc_json / species_blastn / mlst / sistr / amr_card / amr_vfdb / plasmidfinder / summary）
- 5 个 `events`（uploaded → qc_finished → assembly_finished → amr_finished → report_generated）
- 三元证据链：`pipeline_version=salmonella-workflow-v0.1` + database_versions + tool_versions

再次执行会被跳过（`⏭️ 已存在 v1, skipped`）。若 pipeline 升级后再跑，会创建 v2（Immutable + Version First）。

## Step 6 · 生成报告

```bash
python scripts/generate_report.py --sample SAM-TYP-001
# → results/SAM-TYP-001/report/SAM-TYP-001_report.html
```

或 Hermes Agent：

```
> 生成 SAM-TYP-001 的报告
```

报告包含：QC 统计图、组装指标、物种鉴定证据、MLST 等位基因型、血清型详情、AMR/毒力基因表、注释摘要、三元证据链（pipeline + DB + tool 版本）。

## Step 7 · AI 解读

让 Hermes Agent 解读结果，加载 `interpret-results` skill：

```
> SAM-TYP-001 是什么血清型？严重吗？
```

Agent 解读（基于 skill 知识库）：

```
SAM-TYP-001 为 Salmonella Typhimurium（serogroup B），MLST ST19。
Typhimurium 是全球最常见的非伤寒沙门菌血清型之一，与食源性疾病
暴发高度相关。ST19 是其经典序列型。

检出 blaTEM-1（青霉素酶），对青霉素类耐药，但非碳青霉烯酶，
临床严重性为低-中。未检出 CTX-M/NDM/KPC/mcr-1 等关键耐药基因。
```

Deterministic Verifier 自动校验：species ✅、MLST ✅、serotype ✅、AMR 无关键基因 ✅ → 全部 PASS。

## 故障排查

若分析失败：

```bash
# 1. 查看 Snakemake 日志
ls workflows/salmonella/.snakemake/logs/
cat workflows/salmonella/.snakemake/logs/*.snakemake.log | tail -50

# 2. 诊断（Hermes Agent）
> 上次分析失败了，帮我看看
# → 调用 bio_diagnose，解析日志，返回错误类型与修复命令

# 3. 常见问题
#    · 目录被锁：cd workflows/salmonella && snakemake --unlock
#    · Shovill OOM：python scripts/run_analysis.py --sample SAM-TYP-001 --cores 4
#    · 缺失数据库：见参考数据库页

更多见故障排查页。
```

完整错误处理见[故障排查](../reference/troubleshooting.md)。

## 相关案例

- [暴发调查案例](outbreak.md) — 7 株 Salmonella 的 SNP 聚类分析
- [CLI 工具](../usage/cli.md) — 各脚本完整参数
- [Snakemake 管线](../architecture/pipeline.md) — 22 条规则的完整 DAG
