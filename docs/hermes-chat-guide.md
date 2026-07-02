# Hermes-bacmap 交互式使用指南

面向公卫实验室操作员的病原基因组分析操作手册。

支持 **Salmonella / DEC (E. coli) / Shigella / EIEC** 四类病原。

## 1. 启动

```bash
hermes chat
```

启动后进入交互式对话界面，直接用中文提问即可。

## 2. 日常工作流

### 2.1 查看系统中有哪些样本

```
> 有哪些沙门菌样本？
```

系统返回样本列表及分析状态（已完成 / 进行中 / 未开始）。

### 2.2 分析新样本

**前提**：样本 FASTQ 已放置在约定目录，且在 `workflows/salmonella/config/samples.tsv` 中登记。

```
> 分析 SAM-DEC-012
```

系统自动执行完整 pipeline（约 5 分钟/株）：

```
fastp 质控 → Shovill 组装 → 物种鉴定（三基因分流）
  ├─ invA 阳性 → Salmonella 分支（gmlst + SISTR）
  ├─ ipaH 阳性 → Shigella/EIEC 分支（ECTyper + ipaH）
  ├─ uidA 阳性 → DEC 分支（ECTyper + pathotype）
  └─ 均阴性 → 通用 AMR 分析
→ abricate AMR/毒力/质粒 → 汇总报告
```

完成后自动返回关键结果。

### 2.3 查看分析结果

```
> SAM-TYP-001 的分析结果是什么？
```

返回物种、MLST ST、血清型、耐药基因数、毒力基因数、质粒信息。

追问细节：
```
> 具体检出了哪些耐药基因？
```

### 2.4 验证结果可靠性

```
> 验证 SAM-TYP-001 的确定性校验
```

系统运行 Deterministic Verifier，逐项检查：

| 检查项 | 内容 |
|---|---|
| species | invA 确认为 Salmonella |
| mlst | ST 编号有效，7 个 locus 全部检出 |
| serotype | 血清型非空，血清群在已知列表中 |
| amr | 耐药基因名格式合法，标记关键耐药（CTX-M/NDM/KPC/mcr-1） |

结果为 PASS 时可直接出报告；出现"需人工审核"时必须人工复核。

### 2.5 生成报告

```
> 生成 SAM-TYP-001 的分析报告
```

系统生成 HTML 报告（含 Verifier 结果 + 三元证据链），返回文件路径。用浏览器打开即可查看。

### 2.6 跨样本比较

```
> 比较 SAM-TYP-001 和 SAM-TYP-002 的 MLST 和耐药谱
```

系统自动获取两株数据，对比差异，给出流行病学判断。

### 2.7 批量分析

```
> 分析所有未完成的样本
```

系统逐株执行 pipeline（约 5 分钟/株），全部自动完成。

## 3. 完整对话示例

```
> 你好，我是疾控实验室的，想分析一批沙门菌
您好！请问需要什么帮助？

> 先看看系统里有什么样本
系统中共有 6 个 Salmonella 样本，全部已完成分析：
SAM-TYP-001 (Typhimurium), SAM-TYP-002 (Typhimurium), ...

> SAM-INF-005 的耐药情况怎么样？
SAM-INF-005 检出 36 个 AMR 基因（CARD 数据库），包括...

> 这株有没有 ESBL 或碳青霉烯酶？
未检出 blaCTX-M / blaNDM / blaKPC 等关键耐药基因。

> 验证一下
确定性校验全部通过（4/4），无需人工复核。

> 生成报告
报告已生成：results/SAM-INF-005/report/SAM-INF-005_report.html

> 和 SAM-NEW-006 是同一个克隆吗？
两株 MLST 不同（ST-32 vs ST-118），血清型不同（Infantis vs Newport），
不属于同一克隆复合群。
```

## 4. 可用指令一览

### 高层分析指令（日常使用）

| 说什么 | 系统做什么 |
|---|---|
| "列出所有样本" | `bio_list_samples`：列出样本 + 状态 |
| "分析 SAM-XXX" | `bio_analyze_salmonella`：触发完整 pipeline（含 DEC/Shigella 自动分流） |
| "SAM-XXX 的结果" | `bio_get_result`：读取分析摘要 |
| "验证 SAM-XXX" | `bio_verify_result`：Deterministic Verifier 校验 |
| "生成报告" | `bio_generate_report`：生成 HTML 报告 |
| "比较 SAM-001 和 SAM-002" | 自动调两次 `bio_get_result` + 对比 |

### 底层生信指令（高级用户）

| 说什么 | 系统做什么 |
|---|---|
| "统计这个 FASTA 文件" | `bio_seq_stats`：序列长度/GC/N50 |
| "对这个序列做 BLAST" | `bio_blast`：BLAST 搜索 |
| "用 BWA 比对 reads" | `bio_align`：BWA/minimap2 比对 |
| "samtools 处理 BAM" | `bio_samtools`：sort/index/view/depth |
| "变异检测" | `bio_variant`：bcftools variant calling |

## 5. 分析结果字段说明

| 字段 | 含义 | 来源工具 |
|---|---|---|
| Species | 物种判定（Salmonella / not_Salmonella） | blastn invA |
| MLST ST | 7-gene 序列型编号 | gmlst (PubMLST salmonella_2) |
| Serotype | 血清型预测 | SISTR（Salmonella）/ ECTyper（E. coli） |
| Serogroup | 血清群（A/B/C1/C2-C3/D1...） | SISTR |
| O antigen | O 抗原式（如 1,4,[5],12） | SISTR |
| H1:H2 | 鞭毛抗原式（如 i:1,2） | SISTR |
| ipaH | Shigella/EIEC 侵袭基因检测结果 | blastn ipaH |
| Pathotype | DEC 致病型（STEC/EPEC/EIEC/ETEC/EAEC） | call_pathotype.py（基于 vfdb 基因组合） |
| AMR genes | 耐药基因列表 | abricate (CARD) |
| Virulence genes | 毒力基因列表 | abricate (VFDB) |
| Plasmid replicons | 质粒复制子 | abricate (PlasmidFinder) |

## 6. 三元证据链

每份报告附带三元证据链（project.md §4.5），用于监管复核：

```
strain_id:          SAM-TYP-001
pipeline_version:   salmonella-workflow-v0.1
database_versions:  CARD 2026-Apr-3, VFDB 2026-Apr-3, 
                    PlasmidFinder 2026-Apr-3, PubMLST salmonella_2
```

重新分析（如数据库更新后）会生成新版本（v2, v3...），旧版本保留不删（Immutable）。

## 7. 注意事项

- **物种验证**：invA 靶基因方法只确认"是不是 Salmonella"，不做亚种鉴定
- **血清型**：SISTR 是 in silico 预测，与传统血清学可能存在差异
- **耐药基因**：abricate 检出的是基因存在性，不等同于表型耐药（需 MIC 确认）
- **关键耐药**：检出 blaCTX-M / blaNDM / blaKPC / mcr-1 时系统自动标记"需人工审核"
- **组装质量**：N50 < 10 kb 或 contigs > 200 提示组装质量差，可能影响下游分析

## 8. 故障排查

| 问题 | 可能原因 | 解决方案 |
|---|---|---|
| "分析 SAM-XXX" 无响应 | 样本不在 samples.tsv | 在 `workflows/salmonella/config/samples.tsv` 中添加 |
| 组装失败 | FASTQ 质量差或内存不足 | 检查 fastp QC 报告；减少 `--cores` |
| MLST ST = "-" | allele 组合在 scheme 中无对应 ST | 正常情况，查看 allele 编号即可 |
| SISTR 血清型 = "N/A" | 组装质量差或非典型菌株 | 检查 contigs N50；考虑传统血清学 |
| Verifier FAILED | 物种/MLST/血清型异常 | 检查样本是否污染或标签错误 |
| Snakemake 中断 | 网络/电源/进程被杀 | 重新 `分析 SAM-XXX`，自动 resume |
