# Hermes Agent 交互

Hermes Agent 是平台的自然语言编排层。用户用中文或英文描述需求，Agent 路由到对应的 18 个工具与 4 个 Skills 完成分析、检索、解读与报告。

## 启动

```bash
hermes chat
```

进入交互式会话后直接输入指令。Agent 默认加载 `bio-router` skill 做路由决策。

## 示例对话

### 1. 列出样本

```
> 列出所有样本
```

调用 `bio_list_samples`，返回所有样本及分析状态：

```
样本清单（共 10 株）：
  SAM-TYP-001    completed   Salmonella · Typhimurium · ST19
  SAM-ENT-003    completed   Salmonella · Newport · ST45
  SAM-DEC-012    completed   E. coli · O153:H2
  SAM-SHI-013    in-progress Shigella · S. flexneri 2a
  ...
```

### 2. 分析单株

```
> 分析 SAM-TYP-001
```

调用 `bio_analyze_salmonella`，触发 Snakemake 全流程。Agent 会先确认样本存在，然后报告每步进度：

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

### 3. 查询结果

```
> SAM-SHI-013 的 ipaH 是阳性吗？
```

调用 `bio_get_result`，读取 summary 并定位 ipaH 字段：

```
SAM-SHI-013 的物种鉴定结果：ipaH 阳性 ✓
判定为 Shigella / EIEC 谱系。
血清型：S. flexneri 2a（shigella_serotyper）
```

### 4. 自然语言检索

```
> 哪些样本是 Typhimurium？
```

调用 `bio_search_samples(query="Typhimurium")`，按字段加权（serotype 精确匹配 score=10）返回：

```
找到 2 个匹配（按相关度排序）：
  SAM-TYP-001   score=10  serotype=Typhimurium (SISTR)
  SAM-TYP-002   score=10  serotype=Typhimurium (SISTR)
```

更多检索示例：

```
> ST19 的样本有哪些？              → MLST ST 匹配（score=10）
> 哪些样本携带 CRP 耐药基因？       → AMR 基因名匹配（score=9）
> 找带 IncF 质粒的样本              → plasmid 匹配（score=7）
```

### 5. 比较样本与系统发育

```
> 比较 SAM-TYP-001 和 SAM-TYP-002
```

调用 `bio_snp_tree`，返回 cohort 级 Newick 树 + 两两距离：

```
SNP 距离矩阵（7 株 Salmonella，122,598 位点）：
  SAM-TYP-001 ↔ SAM-TYP-002 : 1,666 SNPs   ← 最近，同血清型
  SAM-TYP-001 ↔ SAM-CTX-008 : ~58,000 SNPs
Newick 树已保存：results/snp/core.treefile
```

Agent 会加载 `interpret-results` skill 解读阈值：0–5 SNPs 视为同源传播链。

### 6. 生成报告

```
> 生成 SAM-TYP-001 的报告
```

调用 `bio_generate_report`，生成 HTML 并返回路径。

### 7. 注释基因组

```
> 注释 SAM-TYP-001
```

调用 `bio_annotate`，pyrodigal 预测 CDS + Prokka DB blastp 注释：

```
SAM-TYP-001 注释完成：
  CDS 数：4,872
  已注释：3,541 (72.7%)
  hypothetical：1,331 (27.3%)
文件：results/SAM-TYP-001/annotation/annotation.json
```

### 8. 诊断失败

```
> 上次分析失败了，帮我看看
```

调用 `bio_diagnose`，解析 Snakemake 日志，返回错误类型、根因与修复命令：

```
诊断结果：
  错误类型：OutOfMemory (SIGKILL)
  影响规则：assembly_shovill
  建议修复：
    1. 降低线程：python scripts/run_analysis.py --sample SAM-XXX --cores 4
    2. 限制 Shovill 内存：编辑 assembly.smk 加 --ram 4G
```

## Skills 系统

Hermes-bacmap 注册了 4 个 Skills，采用**三层渐进式加载**：

| Skill | 角色 | 加载时机 |
|---|---|---|
| `bio-router` | 路由器 | 始终加载，决策树 + 工具目录 |
| `run-pipeline` | 管线操作 | 用户请求分析时按需加载 |
| `interpret-results` | 结果解读 | 用户问"这是什么意思"时加载 |
| `bioinfo-analysis` | 通用生信 | 非管线类分析（RNA-seq、long-read 等） |

### 手动加载 Skill

Agent 通常自动加载，也可手动指定：

```
> skill_view("hermes_bacmap:run-pipeline")
> skill_view("hermes_bacmap:interpret-results")
> skill_view("hermes_bacmap:bioinfo-analysis")
```

### bio-router 决策树

```
用户输入
├── "分析 / analyze" + 样本名  → bio_analyze_salmonella + 加载 run-pipeline
├── "注释 / annotate"          → bio_annotate + 加载 interpret-results
├── "X 是什么意思"             → 加载 interpret-results
├── "比较 / compare"           → bio_snp_tree + 加载 interpret-results
├── "搜索 / 找" + 基因/血清型    → bio_search_samples
├── "系统发育树"               → bio_snp_tree
├── "报告 / report"            → bio_generate_report
├── "列出样本"                 → bio_list_samples
└── 其他生信分析               → 加载 bioinfo-analysis
```

详细架构见[Skills 技能系统](../architecture/skills.md)。

## 工具调用边界

Agent 会遵循**三层防御**机制：

```
LLM 生成结果
    ↓
Layer 1: JSON Schema 校验（schemas.py 定义 18 个 tool 的输入输出）
    ↓
Layer 2: Deterministic Verifier（确定性规则校验）
         · species_verdict 必须包含 "Salmonella" 等
         · 关键耐药基因（CTX-M/NDM/KPC/mcr-1）→ NEEDS_REVIEW
    ↓
Layer 3: AI 解读（Skills 知识库）
```

当 Verifier 拦截到可疑结果时，Agent 会明确提示：

```
⚠️ 校验告警：SAM-XXX 检出 blaCTX-M-15（碳青霉烯酶）
   已标记为 NEEDS_REVIEW，需人工复核后再出报告。
```

## 进阶

- [CLI 脚本](cli.md)：脱离 Agent 直接跑批处理
- [Web UI](web-ui.md)：浏览器查看结果
- [单株分析案例](../cases/single-sample.md)：完整端到端实战
- [Skills 技能系统](../architecture/skills.md)：创建自定义 skill
