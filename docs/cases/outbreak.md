# 暴发调查案例

本案例演示对 **7 株 Salmonella 分离株**进行 SNP 系统发育分析，识别潜在暴发聚类。适用场景：食源性疾病暴发溯源、实验室交叉污染排查、传播链确认。

## 场景

某市疾控在两周内收到 7 株 *Salmonella enterica* 分离株，来自不同患者但流行病学信息提示可能存在共同暴露源。需求：

- 用 WGS 确认菌株间亲缘关系
- 识别同源传播链（阈值 ≤5 SNPs）
- 生成可呈交的 SNP 距离矩阵与系统发育树报告

数据集（ENA Gold Standard）：

| 样本 | 血清型 | MLST | 角色 |
|---|---|---|---|
| SAM-TYP-001 | Typhimurium | ST19 | 疑似暴发株 |
| SAM-TYP-002 | Typhimurium | ST19 | 与 001 疑似相关 |
| SAM-ENT-003 | Newport | ST45 | 对照 |
| SAM-ENT-004 | Thompson | ST26 | 对照 |
| SAM-INF-005 | Infantis | ST32 | 新发 MDR 克隆 |
| SAM-NEW-006 | Newport | ST118 | Newport 多样性 |
| SAM-CTX-008 | Typhi | — | 外群（CTX-M-15） |

## Step 1 · 单株分析先行

SNP 管线要求每株已完成组装与物种鉴定：

```bash
# 批量分析全部 7 株
python scripts/run_analysis.py --all

# 检查状态
python scripts/run_analysis.py --status
# 完成应为 7/7
```

或 Hermes Agent：

```
> 分析所有样本
```

确认每株 species_verdict = Salmonella（invA 阳性）。若混入其他物种，SNP cohort 会因参考基因组不匹配而失败。

## Step 2 · 触发 SNP cohort 管线

```bash
python scripts/run_analysis.py --snp
```

或 Hermes Agent：

```
> 跑 SNP 分析
```

触发 5 步流程（详见 [Snakemake 管线](../architecture/pipeline.md#snp-管线5-步)）：

```
✓ snp_calling (×7)        每株 BWA → LT2 参考基因组 → BAM
✓ joint_variant_calling   7 个 BAM 联合 bcftools mpileup → joint VCF
✓ snp_matrix              VCF → FASTA（whole-genome，N 填充缺失）
✓ phylo_tree              IQ-TREE GTR + UFBoot 1000 → Newick
✓ snp_summary             距离矩阵 + 统计 → JSON
```

关键设计：**联合 calling**（非分别 call 后 merge）保证跨样本基因型一致性；**whole-genome 矩阵**保留所有变异位点，仅 4.7% 缺失以 N 填充。

## Step 3 · 入库与报告

```bash
# 先入库单株（若尚未）
python scripts/ingest_results.py --all

# 入库 SNP cohort（创建 cohort:salmonella-snp 对象）
python scripts/ingest_results.py --snp

# 生成 cohort 报告
python scripts/generate_report.py --cohort
# → results/snp/cohort_report.html
```

## Step 4 · 查看系统发育树

```bash
cat results/snp/snp_summary.json | python -m json.tool
```

或 Hermes Agent：

```
> 系统发育树
> 比较 SAM-TYP-001 和 SAM-TYP-002
```

调用 `bio_snp_tree`，返回 Newick 树 + 两两距离矩阵。

### 预期统计

| 指标 | 值 |
|---|---|
| SNP 位点数 | 122,598 |
| 缺失率 | 4.7% |
| Parsimony-informative sites | 55,437 |
| Bootstrap 支持 | 所有内部分支 ≥ 92% |
| 参考基因组 | NC_003197.2（LT2, 4.8 Mb，仅染色体） |

### 预期拓扑

```
                      ┌── SAM-TYP-001 (Typhimurium)
                 ┌────┤
                 │    └── SAM-TYP-002 (Typhimurium)   ← 最近聚类
                 │
                 │         ┌── SAM-ENT-003 (Newport)
                 │      ┌──┤
                 │      │  └── SAM-NEW-006 (Newport)
   ──────────────┤      │
                 │      └── SAM-INF-005 (Infantis)
                 │
                 ├── SAM-ENT-004 (Thompson)
                 │
                 └── SAM-CTX-008 (Typhi)              ← 最长分支（外群）
```

关键拓扑正确性验证：

- Typhimurium 两株（TYP-001 + TYP-002）聚在一起 ✅
- Newport 两株（ENT-003 + NEW-006）聚在一起 ✅
- Typhi（CTX-008）分支最长（0.677）✅

## Step 5 · SNP 距离矩阵解读

Agent 加载 `interpret-results` skill，按阈值表解读：

| 样本对 | SNP 距离 | 解读 |
|---|---|---|
| **TYP-001 ↔ TYP-002** | **1,666** | 同血清型同 ST，但 >50 → 不构成近期传播 |
| ENT-003 ↔ NEW-006 | 中等 | 同血清型 Newport，不同 ST（ST45 vs ST118） |
| TYP-001 ↔ CTX-008 | ~58,000 | 不同血清型，Typhi 作外群 |

### 暴发阈值（来自 interpret-results skill）

| SNP 距离 | 解读 | 公卫行动 |
|---|---|---|
| **0–5** | **同源传播链（高度相关）** | 启动流行病学调查 |
| 6–15 | 可能有流行病学关联 | 结合流行病学信息 |
| 16–50 | 同一谱系 | 持续监测 |
| >50 | 不同谱系 | 排除直接传播 |

### 本案例结论

TYP-001 与 TYP-002 虽同为 Typhimurium ST19，但 **SNP 距离 = 1,666**，远超 5 SNP 阈值，**不支持近期共同源传播**。它们只是同一克隆复合体（clonal complex）的不同谱系成员。

若两株距离 <5 SNPs，则 Agent 会明确提示：

```
⚠️ SAM-XXX 与 SAM-YYY 的 SNP 距离为 3，符合同源传播链阈值。
   建议立即启动流行病学联合调查。
```

## Step 6 · GOM cohort 对象

SNP 结果以 cohort-level ANALYSIS 对象入库（不同于单株的 per-sample 对象）：

```python
GenomeObject(
    object_type="analysis",
    strain_id="cohort:salmonella-snp",          # 去重键前缀
    organism="Salmonella enterica",
    payload={
        "analysis_type": "snp_cohort",
        "samples": ["SAM-TYP-001", ..., "SAM-CTX-008"],
        "tree_newick": "(SAM-TYP-001:0.005,...",
        "pairwise_distances": {"SAM-TYP-001|SAM-TYP-002": 1666, ...},
        "n_snp_sites": 122598,
        "missing_rate": 0.0467,
    },
    pipeline_version="snp-pipeline-v0.3",
)
```

每个样本的 ANALYSIS 对象额外记录 `snp_finished` 事件，建立双向链接。文件产物：

| file_type | 文件 |
|---|---|
| snp_tree_newick | `core.treefile` |
| snp_alignment | `core_snps.fasta` |
| iqtree_report | `core.iqtree` |
| joint_vcf | `joint.vcf.gz` |
| snp_summary | `snp_summary.json` |

详见 [GOM 数据模型 · Cohort SNP 入库](../architecture/gom.md#cohort-snp-入库设计)。

## 关键注意事项

!!! warning "SNP 距离解读边界"
    阈值（0–5 / 6–15 / >50）是经验值，必须结合流行病学信息：

    - 同一血清型 + 同一 ST + 低 SNP 距离 → 强证据
    - 不同来源的参考基因组会导致距离系统性偏高
    - 重组区域（horizontal gene transfer）会虚高距离，必要时用 Gubbins 过滤
    - 低覆盖区域（missing_rate >10%）应谨慎

!!! info "参考基因组选择"
    本案例用 LT2（NC_003197.2，4.8 Mb 染色体）。若分析非 Typhimurium 血清型，可换更近缘参考以降低缺失率。参考必须**仅染色体**，排除质粒（`grep -c "^>" genomes/salmonella_LT2.fasta` 应为 1）。

## 相关

- [单株分析案例](single-sample.md) — 暴发调查的前置步骤
- [Snakemake 管线](../architecture/pipeline.md) — 24 条规则与 SNP 5 步流程
- [Skills 技能系统](../architecture/skills.md) — interpret-results 的 SNP 阈值知识库
- [工具列表](../reference/tools.md) — `bio_snp_tree` 工具详情
