# Hermes-bacmap 功能文档

> **版本**: V0.4 (2026-07-02)
> **状态**: 16 Hermes tools · 21 Snakemake rules · 96 tests · 3 skills · 10 株验证数据集

---

## 目录

1. [系统架构](#1-系统架构)
2. [核心 Python 模块](#2-核心-python-模块)
3. [Hermes Tools（16 个）](#3-hermes-tools16-个)
4. [Snakemake Pipeline（21 条规则）](#4-snakemake-pipeline21-条规则)
5. [Genome Object Model (GOM)](#5-genome-object-model-gom)
6. [物种鉴定系统](#6-物种鉴定系统)
7. [血清型分析](#7-血清型分析)
8. [AMR / 毒力 / 质粒检测](#8-amr--毒力--质粒检测)
9. [SNP 系统发育分析](#9-snp-系统发育分析)
10. [Cohort 分析与 GOM 入库](#10-cohort-分析与-gom-入库)
11. [自然语言样本检索](#11-自然语言样本检索)
12. [Deterministic Verifier（确定性校验）](#12-deterministic-verifier确定性校验)
13. [生信知识 Skills](#13-生信知识-skills)
14. [编排脚本](#14-编排脚本)
15. [CI/CD 与质量保证](#15-cicd-与质量保证)
16. [参考数据库](#16-参考数据库)
17. [Gold Standard 验证数据集](#17-gold-standard-验证数据集)

---

## 1. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户（自然语言中/英文）                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                ┌──────────▼──────────┐
                │   Hermes Agent      │  GLM-5.2 via Z.AI API
                │   (LLM 编排层)       │  16 tools + 3 skills
                └──────────┬──────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                  │
┌────────▼───────┐ ┌───────▼────────┐ ┌──────▼─────────┐
│  L1 固定管线    │ │  L2 确定性校验   │ │  L3 AI 解读     │
│  Snakemake DAG │ │  Verifier       │ │  Skills + 搜索  │
│  21 rules      │ │  21 tests       │ │  FTS5 + 知识库  │
└────────┬───────┘ └───────┬────────┘ └──────┬─────────┘
         │                 │                  │
         └─────────────────┼──────────────────┘
                           │
                ┌──────────▼──────────┐
                │   Genome Object     │  SQLite + WAL + FTS5
                │   Model (GOM)       │  4 tables, 5 indexes
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │   本地文件系统        │  FASTQ / FASTA / VCF / BAM
                └─────────────────────┘
```

### 技术选型

| 层 | 技术 | 理由 |
|---|---|---|
| LLM 推理 | API-key 模式 (GLM-5.2) | 无需 GPU，部署简单 |
| 工作流引擎 | Snakemake 7.32 | Python DSL，AI 可生成/修改规则 |
| 元数据存储 | SQLite + WAL + FTS5 | 零运维，单文件，Hermes 兼容 |
| 文件存储 | 本地文件系统 | 简单可靠，V1.0+ 可迁移 MinIO |
| 包管理 | uv (Python) + pixi (生信工具) | 分离 Python 依赖与生信 CLI |

---

## 2. 核心 Python 模块

| 模块 | 行数 | 职责 |
|---|---|---|
| `tools.py` | 1534 | 16 个 Hermes tool handler 实现 |
| `genome_object_service.py` | 644 | GOM：SQLite CRUD + 版本管理 + 事件 + 文件产物 + FTS5 搜索 |
| `schemas.py` | 541 | 16 个 tool 的 JSON Schema 定义 |
| `gene_scanner.py` | 400 | 通用 BLAST 引擎（替代 abricate 概念），支持任意 abricate 格式数据库 |
| `shigella_serotyper.py` | 207 | Shigella 血清型预测（移植 ShigATyper，58 种血清型） |
| `deterministic_verifier.py` | 186 | 确定性规则校验（species/MLST/serotype/AMR 四层检查） |
| `__init__.py` | 123 | 插件注册（16 tools + 3 skills 自动发现） |
| `species_identifier.py` | 121 | 统一物种鉴定（invA/uidA/ipaH/toxR/tlh 五基因合并为 1 次 BLAST） |
| `ecoh_serotyper.py` | 121 | E. coli O:H 血清型（委托 gene_scanner 做 BLAST） |

---

## 3. Hermes Tools（16 个）

### 3.1 底层生信工具（8 个）

| Tool | 功能 | 底层工具 |
|---|---|---|
| `bio_seq_stats` | FASTA/FASTQ/GenBank 统计（N50、GC、长度分布、质量分布） | Biopython |
| `bio_seq_ops` | 序列操作（反向互补、翻译、GC-skew、motif、ORF、限制位点、k-mer） | Biopython |
| `bio_fastq_qc` | FASTQ 质控 + adapter 检测 | fastp |
| `bio_seq_convert` | 格式转换（FASTA/FASTQ/GenBank/EMBL 等 9 种） | Biopython |
| `bio_blast` | 本地 + 远程（NCBI）BLAST | blastn/blastp/blastx |
| `bio_align` | 序列比对（BWA-MEM / minimap2 / STAR） | bwa, minimap2 |
| `bio_samtools` | SAM/BAM 操作（9 个子命令：index/sort/flagstat/view/depth/faidx/mpileup/consensus/fixmate） | samtools |
| `bio_variant` | 变异检测（mpileup_call/filter/query/annotate/consensus） | bcftools |

### 3.2 高层分析工具（8 个）

| Tool | 功能 | 输入 | 输出 |
|---|---|---|---|
| `bio_analyze_salmonella` | 触发 Snakemake 全流程 | sample_id | summary.json |
| `bio_get_result` | 获取单株紧凑结果摘要 | sample_id | JSON (species/mlst/serotype/amr) |
| `bio_verify_result` | 运行 Deterministic Verifier | sample_id | VerificationResult |
| `bio_generate_report` | 生成 HTML 报告（单株 / 全量 / cohort） | sample_id 或 --cohort | HTML 文件 |
| `bio_list_samples` | 列出所有样本及分析状态 | 无 | 样本状态列表 |
| `bio_gene_scan` | 多数据库基因扫描（CARD/VFDB/ecoh/plasmidfinder/resfinder 等 9 种） | contigs 路径 + 数据库名 | JSON (基因列表 + identity + coverage) |
| `bio_snp_tree` | 获取 cohort-level 系统发育树 + 距离矩阵 | 无 | Newick + pairwise distances |
| `bio_search_samples` | 自然语言样本检索（FTS5 + 字段加权） | 搜索词 | 匹配样本列表（含匹配字段 + 相关度分数） |

### bio_search_samples 加权策略

| 匹配字段 | 分数 | 说明 |
|---|---|---|
| serotype 精确匹配 | 10 | 如搜 "Typhimurium" → sistr=Typhimurium |
| MLST ST 匹配 | 10 | 如搜 "ST2" → mlst_st=2 |
| AMR 基因名匹配 | 9 | 如搜 "CRP" → amr genes 含 CRP |
| MLST 原始文本 | 8 | TSV 中任意字段匹配 |
| plasmid 匹配 | 7 | PlasmidFinder 基因名 |
| strain_id 匹配 | 6 | 样本编号 |
| organism 匹配 | 5 | 物种名 |
| FTS5 全文匹配 | 1 | 降级兜底 |

---

## 4. Snakemake Pipeline（21 条规则）

### 4.1 DAG 概览

```
rule all
  ├── {sample}/report/{sample}_summary.json  (per-sample, ×10)
  │     └── report_summary (collect_summary.py)
  │           ├── qc_fastp → {sample}_fastp.json
  │           ├── assembly_shovill → contigs.fasta
  │           │     └── assembly_stats → assembly_stats.tsv
  │           ├── species_identify → species_id.json
  │           ├── typing_mlst → mlst.tsv
  │           ├── typing_sistr → sistr.json
  │           ├── amr_abricate_vfdb → abricate_vfdb.tsv
  │           ├── amr_abricate_card → abricate_card.tsv
  │           ├── amr_abricate_plasmidfinder → abricate_plasmidfinder.tsv
  │           ├── dec_ecoh_serotype → ecoh_serotype.json
  │           ├── dec_pathotype → pathotype.tsv
  │           └── shigella_serotype → shigella_serotype.json
  │
  └── snp/snp_summary.json  (cohort-level)
        └── snp_summary (generate_snp_summary.py)
              └── phylo_tree → core.treefile + core.iqtree
                    └── snp_matrix → core_snps.fasta
                          └── joint_variant_calling → joint.vcf.gz
                                └── snp_calling (×7) → snps.bam
```

### 4.2 规则清单

| 模块文件 | 规则 | 说明 |
|---|---|---|
| `qc.smk` | `qc_fastp` | fastp 质控 + adapter trimming |
| `assembly.smk` | `assembly_shovill` | Shovill 组装（SPAdes + read correction） |
| | `assembly_stats` | seqkit stats 统计 |
| `species.smk` | `species_identify` | 五基因物种鉴定（1 次 BLAST） |
| `typing_amr.smk` | `typing_mlst` | gmlst (salmonella_2 scheme) |
| | `typing_sistr` | SISTR 血清型 + cgMLST |
| | `amr_abricate_vfdb` | 毒力基因扫描 |
| | `amr_abricate_card` | AMR 耐药基因扫描 |
| | `amr_abricate_plasmidfinder` | 质粒复制子检测 |
| `dec_shigella.smk` | `dec_ecoh_serotype` | E. coli O:H 血清型 |
| | `dec_pathotype` | DEC pathotype 判定 (STEC/EPEC/EIEC/ETEC/EAEC) |
| | `shigella_serotype` | Shigella 血清型 |
| `vpara.smk` | `vpara_targets` | V. parahaemolyticus 物种鉴定 (toxR + tlh) |
| | `vpara_virulence` | 毒力基因检测 (tdh/trh/tlh) |
| `snp.smk` | `snp_calling` | 每株 BWA 比对到参考基因组 |
| | `joint_variant_calling` | 多样本联合变异检测 (bcftools mpileup + call) |
| | `snp_matrix` | 全基因组 SNP 矩阵生成（FASTA，N 填充缺失） |
| | `phylo_tree` | IQ-TREE 最大似然树 (GTR, UFBoot 1000) |
| | `snp_summary` | 距离矩阵 + Newick 汇总 JSON |
| `report.smk` | `report_summary` | collect_summary.py 聚合所有步骤 |
| `Snakefile` | `all` | 主目标（per-sample summaries + cohort SNP） |

---

## 5. Genome Object Model (GOM)

### 5.1 SQLite 表结构

```sql
-- 核心对象表（所有类型共用，JSON 列存储具体内容）
CREATE TABLE genome_objects (
    object_id TEXT NOT NULL,           -- UUID v4
    object_type TEXT NOT NULL,          -- sample|analysis|report|...
    version INTEGER NOT NULL,           -- 单调递增，从 1 开始
    schema_version TEXT NOT NULL,       -- semver "0.1.0"
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    payload_json TEXT NOT NULL,         -- 所有分析结果存于此 JSON
    organism TEXT,                      -- 索引字段
    strain_id TEXT,                     -- 索引字段
    pipeline_version TEXT,              -- ANALYSIS 必填（证据链）
    database_signature TEXT,
    PRIMARY KEY (object_id, version)    -- 复合主键 → 版本化 + 不可变
);

-- 全文搜索虚拟表
CREATE VIRTUAL TABLE genome_objects_fts USING fts5(
    object_type, organism, strain_id, payload_text
);

-- 事件流（Event First 原则）
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    event_type TEXT NOT NULL,           -- uploaded|qc_finished|...|snp_finished
    event_payload TEXT NOT NULL,        -- JSON
    timestamp TEXT NOT NULL
);

-- 文件产物引用（大文件留在文件系统，DB 存路径 + SHA256）
CREATE TABLE file_artifacts (
    artifact_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,               -- 64 字符 hex，写入时实时校验
    size_bytes INTEGER NOT NULL
);
```

### 5.2 核心设计原则

| 原则 | 实现 |
|---|---|
| **Immutable（不可变）** | `delete()` 永远 raise；重复 (object_id, version) raise |
| **Version First** | `create_new_version()` 自动继承元数据，版本号 +1 |
| **Event First** | 每个生命周期阶段都记录事件（uploaded → qc → assembly → ... → snp_finished） |
| **三元证据链** | ANALYSIS 对象必须携带 (strain_id, pipeline_version, database_versions) |
| **JSON-in-SQLite** | 无分类型表，所有结果存入 payload_json，schema-less 弹性 |

### 5.3 GOS 类接口

| 分类 | 方法 | 说明 |
|---|---|---|
| CRUD | `create(obj)` | 创建（重复则 raise GOMImmutableError） |
| | `read(object_id, version)` | 读取特定版本 |
| | `list_by_type(object_type)` | 列出最新版本 |
| | `list_by_organism(organism)` | 按物种筛选 |
| | `search(query)` | FTS5 全文搜索 |
| 版本 | `create_new_version(object_id, payload)` | 创建新版本 |
| | `get_latest_version(object_id)` | 获取最新版本号 |
| | `list_versions(object_id)` | 列出所有版本 |
| 文件 | `register_file_artifact(...)` | 注册文件（含 SHA256 实时校验） |
| | `list_file_artifacts(object_id)` | 列出文件产物 |
| 事件 | `log_event(object_id, type, payload)` | 记录事件 |
| | `list_events(object_id, since)` | 列出事件（支持时间过滤） |

---

## 6. 物种鉴定系统

### 设计

将 5 个物种特异性靶基因合并为 1 个 FASTA 数据库（`species_markers.fasta`），一次 BLAST 调用完成所有物种鉴定。

| 靶基因 | 目标物种 | 参考序列 | 长度 |
|---|---|---|---|
| invA | Salmonella spp. | M90846.1 | 2,176 bp |
| uidA | E. coli / DEC | NC_000913.3 | 1,190 bp |
| ipaH | Shigella / EIEC | NC_004337.2 | 1,827 bp |
| toxR | V. parahaemolyticus | BA000031.2 | 643 bp |
| tlh | V. parahaemolyticus | M36437.1 | 1,302 bp |

### 路由逻辑

```
contigs.fasta
    ↓ BLAST vs species_markers.fasta (1 次调用)
    ↓
    invA 阳性 → Salmonella → 走 Salmonella 分型管线
    uidA 阳性 → E. coli/DEC → 走 DEC 管线 (ecoh_serotyper + pathotype)
    ipaH 阳性 → Shigella/EIEC → 走 Shigella 管线 (shigella_serotyper)
    toxR+tlh 阳性 → V. parahaemolyticus → 走 V.para 管线
```

### 验证结果

10 株 Gold standard 全部正确鉴定（灵敏度 100%，特异性 100%）：
- 7 株 Salmonella → invA 阳性 ✅
- 1 株 E. coli (K-12 MG1655) → uidA 阳性、invA 阴性 ✅
- 1 株 Shigella → ipaH 阳性 ✅
- 1 株 EIEC → ipaH 阳性 ✅

---

## 7. 血清型分析

### 三路分流

| 物种 | 工具 | 数据库 | 输出 |
|---|---|---|---|
| Salmonella | SISTR | salmonella_atdb | serovar + serogroup + O/H antigen |
| DEC / EIEC | ecoh_serotyper (Python) | ecoh_sequences.fasta (753KB, 597 seqs) | O:H serotype + interpretation |
| Shigella | shigella_serotyper (Python) | shigella_ref.fasta (122KB, 95 seqs) | species + serotype (58 种) |

### ecoh_serotyper

- 121 行纯 Python，BLAST 逻辑委托给 gene_scanner（零代码重复）
- 数据库包含 597 条 O/H 抗原序列（vs ECTyper 的 944MB MASH DB）
- 输出：O 型 + H 型 + 完整血清型（如 "O157:H7"）

### shigella_serotyper

- 207 行，移植自 ShigATyper (CFSAN)
- 支持 58 种血清型：
  - S. flexneri: 1a, 1b, 1c, 1d, 2a, 2b, 3a, 3b, 4a, 4b, 5a, 6, 7a, 7b, Y, Yv
  - S. sonnei: I, II
  - S. dysenteriae: 1-15
  - S. boydii: 1-20

### collect_summary.py 血清型分流逻辑

```python
if "Shigella" in species and serotype != "Undetermined":
    primary_serotype = shigella_serotype       # shigella_serotyper
elif ecoh_serotype != "-:-":
    primary_serotype = ecoh_serotype           # ecoh_serotyper (DEC/EIEC)
else:
    primary_serotype = sistr_serovar           # SISTR (Salmonella)
```

---

## 8. AMR / 毒力 / 质粒检测

### 数据库

| 数据库 | 文件大小 | 序列数 | 检测内容 |
|---|---|---|---|
| CARD | 6.5 MB | ~5,000 | AMR 耐药基因 |
| VFDB | 6.3 MB | ~4,000 | 毒力因子 |
| PlasmidFinder | 437 KB | ~400 | 质粒复制子 |

### 集成方式

通过 Snakemake 规则调用 `abricate`（3 个并行规则）：
```
amr_abricate_vfdb:        abricate --db vfdb {contigs} → abricate_vfdb.tsv
amr_abricate_card:        abricate --db card {contigs} → abricate_card.tsv
amr_abricate_plasmidfinder: abricate --db plasmidfinder {contigs} → abricate_plasmidfinder.tsv
```

### gene_scanner 通用引擎

`bio_gene_scan` Hermes tool 提供运行时动态扫描能力，支持 9 种数据库：
`card, vfdb, ecoh, plasmidfinder, resfinder, ncbi, megares, victors, ecoli_vf`

底层由 `gene_scanner.py` (400 行) 驱动，检查 BLAST 返回码（非零 raise RuntimeError，防止静默假阴性）。

---

## 9. SNP 系统发育分析

### 流水线（5 步）

```
步骤 1: snp_calling (每株)
  raw FASTQ → bwa mem (vs LT2 参考基因组) → samtools sort → BAM

步骤 2: joint_variant_calling (多样本联合)
  7 个 BAM → bcftools mpileup (联合) → bcftools call → joint VCF
  ※ 关键：联合 calling 保证跨样本基因型一致性

步骤 3: snp_matrix (全基因组 SNP 矩阵)
  joint VCF → Python 解析 → FASTA alignment
  策略：whole-genome mode（保留所有变异位点，缺失用 N 填充）

步骤 4: phylo_tree (系统发育树)
  FASTA → IQ-TREE -m GTR -bb 1000 -alrt 1000
  输出：Newick treefile + IQ-TREE 报告

步骤 5: snp_summary (距离矩阵)
  treefile + FASTA → JSON (Newick + pairwise distances + 统计)
```

### 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 变异检测策略 | **Joint calling**（非分别 call 后 merge） | 避免跨样本基因型不一致 |
| 矩阵策略 | **Whole-genome**（非 strict core） | 保留所有变异位点，N 填充缺失（4.7%），无信号丢失 |
| 对齐格式 | **FASTA**（非 PHYLIP） | 无 10 字符名称截断限制 |
| 参考基因组 | NC_003197.2 (S. Typhi LT2, 4.8Mb) | 仅染色体，排除质粒 |

### 验证结果（7 株 Salmonella）

| 指标 | 值 |
|---|---|
| SNP 位点数 | 122,598 |
| 缺失率 | 4.7% |
| Parsimony-informative sites | 55,437 |
| Bootstrap 支持 | 所有内部分支 ≥ 92% |

**拓扑正确性验证**：
- Typhimurium 两株 (TYP-001 + TYP-002) 聚在一起，SNP 距离 = 1,666 ✅
- Newport 两株 (ENT-003 + NEW-006) 聚在一起 ✅
- Typhi (CTX-008) 分支最长 (0.677) ✅

---

## 10. Cohort 分析与 GOM 入库

### Cohort 对象设计

SNP 分析是 **多样本（cohort-level）** 结果，不能放入 per-sample 的 GOM 对象。解决方案：

```
创建 1 个 cohort-level ANALYSIS GenomeObject:
  strain_id = "cohort:salmonella-snp"   ← 去重键
  organism = "Salmonella enterica"
  payload = {
      "analysis_type": "snp_cohort",
      "samples": ["SAM-TYP-001", ...],   ← 7 个样本
      "tree_newick": "(SAM-TYP-001:0.005,...",
      "pairwise_distances": {"SAM-TYP-001|SAM-TYP-002": 1666, ...},
      "n_snp_sites": 122598,
      "missing_rate": 0.0467
  }
  pipeline_version = "snp-pipeline-v0.3"
```

### 文件产物注册

| file_type | 文件 | 说明 |
|---|---|---|
| snp_tree_newick | core.treefile | Newick 树文件 |
| snp_alignment | core_snps.fasta | SNP 比对序列 |
| iqtree_report | core.iqtree | IQ-TREE 完整报告 |
| joint_vcf | joint.vcf.gz | 联合 VCF |
| snp_summary | snp_summary.json | 汇总 JSON |

### 样本链接

每个样本的 ANALYSIS 对象上记录 `snp_finished` 事件，payload 包含 cohort object_id 引用：

```python
gos.log_event(sample_object_id, "snp_finished", {
    "cohort_object_id": cohort_oid,
    "strain_id": "SAM-TYP-001",
})
```

### 入库命令

```bash
# 先入库所有单株结果
python scripts/ingest_results.py --all

# 再入库 SNP cohort
python scripts/ingest_results.py --snp
```

### 幂等性

相同 pipeline_version 的重复入库会被跳过（`⏭️ 已存在 v1, skipped`）。

---

## 11. 自然语言样本检索

### bio_search_samples 工具

用户可以用自然语言查询已入库的样本结果：

```
用户："哪些样本是 Typhimurium？"
→ bio_search_samples(query="Typhimurium")
→ 返回 2 个匹配（score=10，serotype 精确匹配）

用户："ST19 的样本有哪些？"
→ bio_search_samples(query="ST19")
→ 返回匹配 ST19 的样本（score=10，MLST 匹配）

用户："哪些样本携带 CRP 耐药基因？"
→ bio_search_samples(query="CRP")
→ 返回所有 AMR 基因含 CRP 的样本（score=9）
```

### 搜索流程

```
1. 遍历所有 ANALYSIS 对象（排除 cohort: 前缀）
2. 对每个对象，检查 payload 中各字段是否匹配查询：
   - serotype.sistr → score 10
   - mlst ST 数字（支持 "ST2" 格式） → score 10
   - AMR 基因名 → score 9
   - plasmid 基因名 → score 7
   - organism → score 5
   - strain_id → score 6
   - FTS5 全文 → score 1（降级兜底）
3. 去重（多版本只保留最新）
4. 按 score 降序排列，返回前 50 条
```

---

## 12. Deterministic Verifier（确定性校验）

### 三层防御机制

```
LLM 生成结果 → Layer 1: JSON Schema 校验 → Layer 2: 确定性规则校验 → Layer 3: AI 解读
                                        ↑
                                  Deterministic Verifier
```

### 校验规则（4 类）

| 检查类别 | 规则 | 失败处理 |
|---|---|---|
| Species | species_verdict 包含 "Salmonella" | ❌ FAIL |
| MLST | mlst 字段非空且有 ST 数字 | ⚠️ WARN |
| Serotype | serotype.sistr 非空 | ⚠️ WARN |
| AMR | 关键耐药基因 (CTX-M/NDM/KPC/mcr-1) 触发人工审核 | ⚠️ NEEDS_REVIEW |

### 代码接口

```python
from hermes_bacmap.deterministic_verifier import DeterministicVerifier

v = DeterministicVerifier()
result = v.verify_all(summary_dict)
# result.passed → bool
# result.checks → list[CheckResult]
# result.needs_human_review → bool
# result.failed_count → int
```

### 测试覆盖

21 个 TDD 测试覆盖所有规则路径（正例 + 反例 + 边界情况）。

---

## 13. 生信知识 Skills

| Skill | 文件 | 用途 |
|---|---|---|
| `analyze-salmonella` | 102 行 | Salmonella 端到端分析操作指南（状态检查 → 启动 → 解读 → 恢复） |
| `bioinfo-analysis` | 86 行 | 通用生信决策树（FASTQ→QC, FASTA→stats, BAM→samtools） |
| `interpret-results` | 168 行 | 结果解读知识库（血清型/MLST/AMR/SNP 距离/毒力基因临床意义） |

### interpret-results 内容概览

| 章节 | 内容 |
|---|---|
| Salmonella 血清型 | Kauffmann-White 方案解读；6 种临床重要血清型；monophasic Typhimurium |
| E. coli/DEC | 5 种 pathotype (STEC/EPEC/EIEC/ETEC/EAEC)；Big Six non-O157；Shigella vs EIEC |
| MLST | ST19=Typhimurium, ST11=Enteritidis, ST131=ExPEC 等临床意义 |
| AMR 基因 | β-内酰胺酶分级（carbapenemase > ESBL > AmpC > penicillinase）；临床严重性分级 |
| SNP 距离 | 0-5 SNPs=同源传播链；6-15=可能相关；>50=不同谱系；注意事项 |
| 毒力基因 | SPI-1/SPI-2 分泌系统；spv 毒力质粒；sop 效应蛋白 |
| 报告指南 | 5 条结果摘要原则（物种确认→可执行发现→非常规标记→上下文→局限性） |

### 注册机制

`__init__.py` 自动发现 `skills/*/SKILL.md`，通过 `ctx.register_skill()` 注册到 Hermes。

---

## 14. 编排脚本

| 脚本 | 行数 | 功能 |
|---|---|---|
| `run_analysis.py` | 255 | 端到端编排器（--sample / --all / --snp / --status） |
| `ingest_results.py` | 385 | GOM 入库（--sample / --all / --snp，含去重+版本管理） |
| `generate_report.py` | 336 | HTML 报告（--sample / --all / --cohort） |
| `download_gold_standard.py` | 200 | ENA FASTQ 下载（aria2c 多线程 + MD5 校验） |
| `generate_snp_matrix.py` | 179 | VCF → FASTA SNP 矩阵（whole-genome mode） |
| `collect_summary.py` | 120 | Snakemake 脚本：聚合所有步骤结果为 summary.json |
| `generate_snp_summary.py` | 107 | treefile + FASTA → snp_summary.json |
| `call_pathotype.py` | 75 | DEC pathotype 判定（stx1/stx2/eae/ipaH/est/elt/aggR） |
| `assemble_gold_standard.sh` | 60 | 批量 Shovill 组装 |
| `species_validation_invA.sh` | 67 | invA 物种验证（bwa mem + samtools） |
| `assembly_validation_blastn.sh` | 80 | 组装子 blastn 物种验证 |

### run_analysis.py 关键特性

- **样本验证**：未知 sample_id 报错并列出有效样本
- **超时保护**：subprocess.run timeout=7200s，防止无限挂起
- **环境保留**：`{**os.environ, PATH=...}` 保留 HOME/TMPDIR 等
- **失败诊断**：输出 3 步诊断建议（检查日志 → 解锁 → 重试）
- **部分完成检测**：--all 模式下，缺失 summary 的样本会被统计并返回 exit 1
- **SNP 支持**：--snp 触发 cohort 级 SNP 管线

---

## 15. CI/CD 与质量保证

### CI Pipeline（6 jobs）

| Job | 内容 | 触发 |
|---|---|---|
| `lint` | ruff check + ruff format --check | PR + push to main |
| `typecheck` | mypy --strict src/hermes_bacmap/ | PR + push to main |
| `unit-tests` | pytest --cov + Codecov 上传 | PR + push to main |
| `pre-commit` | .pre-commit-config.yaml hooks | PR + push to main |
| `security-scan` | pip-audit --strict (CVE 检查) | PR + push to main |
| `changelog-check` | 强制 CHANGELOG.md 更新 | PR to main |

### 测试覆盖

| 测试文件 | 测试数 | 覆盖范围 |
|---|---|---|
| `test_genome_object_service.py` | 50 | GOM schema/CRUD/版本/文件/事件/工厂函数 |
| `test_deterministic_verifier.py` | 21 | Verifier 四类规则（正例/反例/边界） |
| `test_cohort_ingest.py` | 9 | Cohort 创建/去重/事件/链接/版本/文件/查询/树/距离 |
| `test_env.py` | 5 | 环境验证（Python/pixi/工具链） |
| **合计** | **96** | |

### Pre-commit Hooks

ruff + mypy --strict + markdownlint + trailing-whitespace + detect-secrets

---

## 16. 参考数据库

### 物种鉴定数据库

| 文件 | 大小 | 内容 |
|---|---|---|
| `species_markers.fasta` | 8.3 KB | 5 基因合并库（invA + uidA + ipaH + toxR + tlh） |
| `salmonella_invA.fasta` | 2.3 KB | invA 独立库（M90846.1, 2176bp） |
| `uidA_ecoli.fasta` | 1.3 KB | uidA (NC_000913.3, 1190bp) |
| `ipaH_shigella.fasta` | 1.9 KB | ipaH (NC_004337.2, 1827bp) |
| `toxR_vpara.fasta` | 1.3 KB | toxR (BA000031.2) |
| `tlh_vpara.fasta` | 1.7 KB | tlh (M36437.1) |

### AMR / 毒力 / 质粒数据库

| 文件 | 大小 | 来源 |
|---|---|---|
| `card_sequences.fasta` | 6.5 MB | CARD (Comprehensive Antibiotic Resistance Database) |
| `vfdb_sequences.fasta` | 6.3 MB | VFDB (Virulence Factor Database) |
| `plasmidfinder_sequences.fasta` | 437 KB | PlasmidFinder (CGE) |

### 血清型数据库

| 文件 | 大小 | 内容 |
|---|---|---|
| `ecoh_sequences.fasta` | 782 KB | E. coli O/H 抗原（597 seqs） |
| `shigella_ref.fasta` | 122 KB | Shigella 抗原（95 seqs，移植自 ShigATyper） |

### SNP 参考基因组

| 文件 | 大小 | 内容 |
|---|---|---|
| `salmonella_LT2_ref.fasta` | 4.7 MB | NC_003197.2 (S. enterica LT2 染色体, 4,857,450bp) |

### V. parahaemolyticus 毒力数据库

| 文件 | 大小 | 内容 |
|---|---|---|
| `tdh_vpara.fasta` | 1.2 KB | tdh (D90238.1, 耐热直接溶血素) |
| `trh_vpara.fasta` | 1.7 KB | trh (AY586619.1, TDH-related 溶血素) |
| `vpara_targets.fasta` | 5.7 KB | toxR + tlh 合并库 |

---

## 17. Gold Standard 验证数据集

### 10 株菌株

| 样本编号 | 物种 | 血清型 | MLST | 来源 | 用途 |
|---|---|---|---|---|---|
| SAM-TYP-001 | S. enterica | Typhimurium | ST19 | ENA | 标准株 |
| SAM-TYP-002 | S. enterica | Typhimurium | ST19 | ENA | 重复（SNP 验证） |
| SAM-ENT-003 | S. enterica | Newport | ST45 | ENA | 血清型多样性 |
| SAM-ENT-004 | S. enterica | Thompson | ST26 | ENA | 血清型多样性 |
| SAM-INF-005 | S. enterica | Infantis | ST32 | ENA | 新发 MDR 克隆 |
| SAM-NEW-006 | S. enterica | Newport | ST118 | ENA | Newport 多样性 |
| SAM-CTX-008 | S. enterica | Typhi | — | ENA | CTX-M-15 + 系统发育外群 |
| SAM-DEC-012 | E. coli | O153:H2 | — | ENA | DEC 阴性对照 |
| SAM-SHI-013 | Shigella | S. flexneri 2a | — | ENA | ipaH 验证 |
| SAM-EIEC-014 | E. coli (EIEC) | O152:H28 | — | ENA | ipaH + ecoh 双验证 |

### 验证矩阵

| 验证项 | 结果 |
|---|---|
| 物种鉴定（invA/uidA/ipaH） | 10/10 ✅ |
| Salmonella 血清型 (SISTR) | 7/7 ✅ |
| DEC 血清型 (ecoh_serotyper) | 3/3 ✅ |
| Shigella 血清型 (shigella_serotyper) | 1/1 ✅ |
| SNP 系统发育树拓扑 | ✅（Newport 聚类 + Typhi 最长分支） |
| SNP 距离矩阵 | ✅（TYP-001 vs TYP-002 = 1,666 SNPs，最低） |

---

## 附录：环境与依赖

### Python 依赖 (uv + pyproject.toml)

```
biopython >= 1.83     # 序列操作
pydantic >= 2.0       # 数据模型
pytest >= 8.0         # 测试
ruff >= 0.5           # lint + format
mypy >= 1.10          # 类型检查
```

### 生信工具 (pixi + pixi.toml)

```
fastp >= 1.3.5        # QC
shovill >= 1.1.0      # 组装
blast >= 2.16         # BLAST
bwa >= 0.7.17         # 比对
samtools >= 1.20      # BAM 操作
bcftools >= 1.20      # 变异检测
seqkit >= 2.8         # 序列统计
sistr_cmd >= 1.1.3    # Salmonella 血清型
abricate >= 1.4.0     # AMR/毒力/质粒
iqtree >= 3.1.2       # 系统发育树
snakemake 7.32.*      # 工作流引擎
```

### 独立环境

```
.venv-gmlst/          # Python 3.12 (gmlst 需要 ≥3.12)
```
