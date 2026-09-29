# Interacting with the Hermes Agent

The Hermes Agent is the platform's natural-language orchestration layer. Users describe their needs in Chinese
or English, and the Agent routes to the corresponding 18 tools and 4 Skills to complete analysis, retrieval,
interpretation, and reporting.

## Starting

```bash
hermes chat
```

Once inside the interactive session, type instructions directly. The Agent loads the `bio-router` skill by default for routing decisions.

## Example Conversations

### 1. Listing samples

```
> 列出所有样本
```

Calls `bio_list_samples`, returning all samples with their analysis status:

```
样本清单（共 10 株）：
  SAM-TYP-001    completed   Salmonella · Typhimurium · ST19
  SAM-ENT-003    completed   Salmonella · Newport · ST45
  SAM-DEC-012    completed   E. coli · O153:H2
  SAM-SHI-013    in-progress Shigella · S. flexneri 2a
  ...
```

### 2. Analyzing an isolate

```
> 分析 SAM-TYP-001
```

Calls `bio_analyze_pathogen`, triggering the full Snakemake workflow. The Agent first confirms the sample exists, then reports progress at each step:

```
启动分析 SAM-TYP-001 ...
✓ QC (fastp)
✓ Assembly (Shovill, N50 = 215 kb)
✓ Species identify → Salmonella (invA+)
✓ MLST → ST19
✓ Serotype → Typhimurium (SISTR)
✓ AMR → blaTEM-1, qnrB
报告已生成：results/SAM-TYP-001/report/SAM-TYP-001_report.html
```

### 3. Querying results

```
> SAM-SHI-013 的 ipaH 是阳性吗？
```

Calls `bio_get_result`, reads the summary, and locates the ipaH field:

```
SAM-SHI-013 的物种鉴定结果：ipaH 阳性 ✓
判定为 Shigella / EIEC 谱系。
血清型：S. flexneri 2a（shigella_serotyper）
```

### 4. Natural-language search

```
> 哪些样本是 Typhimurium？
```

Calls `bio_search_samples(query="Typhimurium")` and returns results weighted by field (exact serotype match scores 10):

```
找到 2 个匹配（按相关度排序）：
  SAM-TYP-001   score=10  serotype=Typhimurium (SISTR)
  SAM-TYP-002   score=10  serotype=Typhimurium (SISTR)
```

More search examples:

```
> ST19 的样本有哪些？              → MLST ST 匹配（score=10）
> 哪些样本携带 CRP 耐药基因？       → AMR 基因名匹配（score=9）
> 找带 IncF 质粒的样本              → plasmid 匹配（score=7）
```

### 5. Comparing samples and phylogeny

```
> 比较 SAM-TYP-001 和 SAM-TYP-002
```

Calls `bio_snp_tree`, returning the cohort-level Newick tree + pairwise distances:

```
SNP 距离矩阵（7 株 Salmonella，122,598 位点）：
  SAM-TYP-001 ↔ SAM-TYP-002 : 1,666 SNPs   ← 最近，同血清型
  SAM-TYP-001 ↔ SAM-CTX-008 : ~58,000 SNPs
Newick 树已保存：results/snp/core.treefile
```

The Agent loads the `interpret-results` skill to interpret thresholds: 0–5 SNPs is treated as a common-source transmission chain.

### 6. Generating a report

```
> 生成 SAM-TYP-001 的报告
```

Calls `bio_generate_report`, generates the HTML, and returns the path.

### 7. Annotating a genome

```
> 注释 SAM-TYP-001
```

Calls `bio_annotate`: pyrodigal predicts CDSs + Prokka DB blastp annotates them:

```
SAM-TYP-001 注释完成：
  CDS 数：4,872
  已注释：3,541 (72.7%)
  hypothetical：1,331 (27.3%)
文件：results/SAM-TYP-001/annotation/annotation.json
```

### 8. Diagnosing failures

```
> 上次分析失败了，帮我看看
```

Calls `bio_diagnose`, parses the Snakemake log, and returns the error type, root cause, and fix commands:

```
诊断结果：
  错误类型：OutOfMemory (SIGKILL)
  影响规则：assembly_shovill
  建议修复：
    1. 降低线程：python scripts/run_analysis.py --sample SAM-XXX --cores 4
    2. 限制 Shovill 内存：编辑 assembly.smk 加 --ram 4G
```

## The Skills System

Hermes-bacmap registers 4 Skills using **three-layer progressive loading**:

| Skill | Role | Loaded when |
|---|---|---|
| `bio-router` | Router | Always loaded; decision tree + tool catalog |
| `run-pipeline` | Pipeline operations | Loaded on demand when the user requests analysis |
| `interpret-results` | Result interpretation | Loaded when the user asks "what does this mean" |
| `bioinfo-analysis` | General bioinformatics | Non-pipeline analyses (RNA-seq, long-read, etc.) |

### Manually Loading a Skill

The Agent usually loads them automatically, but you can also specify one manually:

```
> skill_view("hermes_bacmap:run-pipeline")
> skill_view("hermes_bacmap:interpret-results")
> skill_view("hermes_bacmap:bioinfo-analysis")
```

### bio-router Decision Tree

```
用户输入
├── "分析 / analyze" + 样本名  → bio_analyze_pathogen + 加载 run-pipeline
├── "注释 / annotate"          → bio_annotate + 加载 interpret-results
├── "X 是什么意思"             → 加载 interpret-results
├── "比较 / compare"           → bio_snp_tree + 加载 interpret-results
├── "搜索 / 找" + 基因/血清型    → bio_search_samples
├── "系统发育树"               → bio_snp_tree
├── "报告 / report"            → bio_generate_report
├── "列出样本"                 → bio_list_samples
└── 其他生信分析               → 加载 bioinfo-analysis
```

For the detailed architecture, see the [Skills system](../architecture/skills.md).

## Tool-Call Boundaries

The Agent follows a **three-layer defense** mechanism:

```
LLM 生成结果
    ↓
Layer 1: JSON Schema 校验（schemas.py 定义 24 个 tool 的输入输出）
    ↓
Layer 2: Deterministic Verifier（确定性规则校验）
         · species_verdict 必须包含 "Salmonella" 等
         · 关键耐药基因（CTX-M/NDM/KPC/mcr-1）→ NEEDS_REVIEW
    ↓
Layer 3: AI 解读（Skills 知识库）
```

When the Verifier intercepts a suspicious result, the Agent clearly warns:

```
⚠️ 校验告警：SAM-XXX 检出 blaCTX-M-15（碳青霉烯酶）
   已标记为 NEEDS_REVIEW，需人工复核后再出报告。
```

## Going Further

- [CLI scripts](cli.md): run batch jobs without the Agent
- [Web UI](web-ui.md): view results in the browser
- [Single-isolate case study](../cases/single-sample.md): a complete end-to-end walkthrough
- [Skills system](../architecture/skills.md): create custom skills


## Database Deployment

The first run after installation prompts you to deploy the identification databases. Just say in the conversation:

```
> 安装 ANI 鉴定库
> 数据库装好了吗？
```

The AI automatically calls `bio_db_setup` to select a tier and deploy in the background; `bio_db_status` tracks the progress.

## Multi-Method Identification Comparison

```
> 比较 SAM-TYP-001 的物种鉴定结果
```

The AI calls `bio_species_compare` and outputs each method's (marker / ANI / sourmash) species verdict, confidence, agreement, and arbitration conclusion.
