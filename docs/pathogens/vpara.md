# *Vibrio parahaemolyticus*

## 物种鉴定

- **Species**: *Vibrio parahaemolyticus*
- **Target genes**: `toxR` + `tlh`
- **toxR**: 种特异性转录调控因子（BA000031.2）
- **tlh**: thermolabile hemolysin，物种标记（M36437.1）
- **Routing rule**: toxR 或 tlh 阳性 → V. parahaemolyticus pipeline

## 毒力基因

| 基因 | 功能 | 临床意义 |
|---|---|---|
| `tdh` | thermostable direct hemolysin | Kanagawa phenomenon |
| `trh` | TDH-related hemolysin | 协同增强致病性 |
| `tlh` | species marker | ubiquitous，不直接致病 |

## 毒力组合临床判读

| tdh | trh | 临床意义 |
|---|---|---|
| + | + | 高致病性，多为 pandemic clone RIMD 2210633 |
| + | - | Kanagawa 阳性，胃肠炎 |
| - | + | 胃肠炎（发生率较低） |
| - | - | 通常为环境株，非致病 |

---

## O/K 血清型分型

### 概述

VpaSerotyper 从组装好的 contigs 预测 *V. parahaemolyticus* 的 O（脂多糖）和 K（荚膜多糖）血清型。引擎移植自 [vpautils](https://github.com/indexofire/vpautils)，采用 Kaptive 式三阶段算法。

### 算法管线

```
组装 contigs
    |
A. minimap2 比对 -> 提取 locus 区域 contigs
    |
B. sourmash k-mer containment -> 排序候选 locus
    |
C. 基因级别验证 -> 每个基因的覆盖度/一致性
    |
D. 决策 -> 置信度分级（Perfect/High/Medium/Low/Unknown）
```

| 阶段 | 方法 | 目的 |
|---|---|---|
| A. Locus 提取 | minimap2 (mappy) splice 模式 | 从样本 contigs 中提取与参考 locus 对齐的区域 |
| B. K-mer 排序 | sourmash MinHash containment | 快速筛选最匹配的参考 locus（>30% containment） |
| C. 基因验证 | minimap2 逐基因比对 | 每个参考基因在样本中的覆盖度和一致性 |
| D. 置信度决策 | 规则引擎 | 综合基因缺失数、覆盖度、一致性、边界基因、片段化 |

### 置信度分级

| 等级 | 条件 | 含义 |
|---|---|---|
| **Perfect** | 单 contig + 0 缺失 + identity > 95% | 完整匹配，高置信度分型 |
| **High** | <=1 缺失 + coverage > 90% + identity > 90% | 高置信度，可报告 |
| **Medium** | <=4 缺失 + identity > 80% | 中置信度，可报告但需注意 |
| **Low** | identity > 80%（通过其他条件） | 低置信度，建议补充验证 |
| **Unknown** | >4 缺失 或 边界基因缺失 | 不可分型 |

### 参考数据库

```
data/reference/vpa_serotype/ (33 MB)
├── ref_seqs.fasta      7.0 MB   195 条参考 locus 序列
├── gene_refs.fasta     6.4 MB   基因级别参考序列
├── ref_sketches.sig    1.4 MB   sourmash MinHash 签名（k=21, scaled=100）
├── ref_meta.pkl        518 KB   locus 元数据（基因位置、类型、名称）
├── ref_meta.sig        64 B     HMAC 签名（完整性校验）
├── OAgc.gbk            1.8 MB   O-antigen 基因簇 GenBank 源文件
└── CPSgc.gbk           16 MB    K-capsule 基因簇 GenBank 源文件
```

| 类型 | Locus 数 | 示例 |
|---|---|---|
| O-antigen (OL) | 32 | OL1, OL2, OL3, OL4, OL5, ... OL11, ... |
| K-antigen (KL) | 163 | KL1, KL6, KL12, KL15, KL28, ... |

### 使用方式

#### 命令行（Snakemake）

```bash
# 单样本（自动触发组装 -> 血清型）
python scripts/run_analysis.py --sample SAM-VPA-001
```

Snakemake 会自动执行 `vpara_serotype` 规则，输出到：
```
results/{sample}/vpa/vpa_serotype.json
```

#### Hermes Agent

```
hermes chat
> 对 SAM-VPA-001 的 contigs 做血清型分型
```

调用 `bio_vpa_serotype` tool，返回 JSON 结果。

#### Python API

```python
from hermes_bacmap.typing.vpa_serotyper import VpaSerotyper

s = VpaSerotyper()
result = s.analyze("contigs.fasta", "SAM-VPA-001")

print(result.predicted_serotype)  # "O3:K6"
print(result.o_confidence)        # "Perfect"
print(result.k_confidence)        # "Perfect"
```

### 输出字段说明

#### SerotypeResult 基本字段

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `sample` | str | 样本编号 | SAM-VPA-001 |
| `predicted_serotype` | str | 预测血清型 | O3:K6 |
| `o_locus` | str | O-antigen 最佳匹配 locus | OL3 |
| `o_confidence` | str | O 置信度 | Perfect |
| `o_coverage` | float | O 基因覆盖率 (%) | 100.0 |
| `o_identity` | float | O 平均一致性 (%) | 100.0 |
| `o_missing_genes` | str | O 缺失基因（分号分隔） | None |
| `o_alerts` | str | O 告警 | None |
| `k_locus` | str | K-antigen 最佳匹配 locus | KL6 |
| `k_confidence` | str | K 置信度 | Perfect |
| `k_coverage` | float | K 基因覆盖率 (%) | 100.0 |
| `k_identity` | float | K 平均一致性 (%) | 99.98 |
| `k_missing_genes` | str | K 缺失基因 | None |
| `k_alerts` | str | K 告警 | None |

#### 引擎详细输出（enable_detail=True）

| 字段 | 说明 |
|---|---|
| `O/K_Expected_In_Locus` | 基因命中在预期 locus contig 上的数量/百分比 |
| `O/K_Expected_Outside` | 基因命中在 locus 外（其他 contig）的数量 |
| `O/K_Other_In_Locus` | 非该 locus 的其他基因出现在 locus 区域（可能重组） |
| `O/K_Truncated` | 覆盖度 <100% 的基因列表 |
| `O/K_Length_Discrepancy` | 样本 locus 总长度 - 参考长度（负值=缺失） |
| `O/K_Genes_Detail` | 每个基因的 identity/coverage/status |
| `O/K_Detail` | 引擎诊断说明（当置信度非 Perfect 时） |
| `_gene_details` | 逐基因详细 dict（gene, identity, coverage, status, contig, position） |

#### 告警类型

| 告警 | 含义 |
|---|---|
| `Fragmented` | Locus 跨多个 contig（组装不完整） |
| `MissingBoundary(gene1,gene2)` | 边界基因缺失（coaD/rfaD/glpX），导致不可分型 |

### 验证结果

#### RIMD 2210633（O3:K6 全球大流行株）

| 指标 | O 抗原 (OL3) | K 抗原 (KL6) |
|---|---|---|
| 置信度 | Perfect | Perfect |
| 基因覆盖 | 26/26 (100%) | 31/31 (100%) |
| 平均一致性 | 100.00% | 99.98% |
| 缺失基因 | 无 | 无 |
| 长度差异 | 0 bp | 0 bp |
| 耗时 | <1s | <1s |

#### 批量验证（10 株）

| 样本 | 期望 | 预测 | 准确 |
|---|---|---|---|
| GCA_000706825.2 | O4:K12 | O4:K12 | OK |
| GCA_000706905.2 | O4:K12 | O4:K12 | OK |
| GCA_000707185.2 | O3:K12 | O3:K12 | OK |
| GCA_000707465.2 | O11:K15 | O11:K15 | OK |

**准确率：4/4 已知血清型 = 100%，平均 2.6 秒/株。**

### 复杂样本诊断示例

GCA_000707465.2 (O11:K15) 的 K 抗原报告了 Medium 置信度：

| 维度 | 值 | 说明 |
|---|---|---|
| 缺失基因 | KL15_022, 023, 024, 025 | 4 个连续基因缺失 |
| 长度差异 | -4855 bp | K locus 比参考短 4855 bp |
| 截断基因 | KL15_002 (85.9%), KL15_018 (81.8%) | 部分基因不完整 |
| 其他基因入侵 | 8 | 可能有重组 |

引擎正确识别为 K15，但因基因缺失降低了置信度。

### 依赖

| 依赖 | 版本 | 用途 |
|---|---|---|
| `mappy` (minimap2) | >= 2.24 | Python 绑定，序列对齐 |
| `sourmash` | >= 4.8 | MinHash k-mer containment |
| `ref_seqs.fasta` + 索引 | — | minimap2 参考序列 |
| `ref_sketches.sig` | — | sourmash 签名 |
| `ref_meta.pkl` | — | locus 元数据 |

### Hermes Tool

| 属性 | 值 |
|---|---|
| Tool name | `bio_vpa_serotype` |
| 输入 | contigs_path (FASTA) |
| 输出 | JSON (SerotypeResult) |
| 描述 | 预测 V. parahaemolyticus O/K 血清型 |

### Snakemake 规则

```python
rule vpara_serotype:
    input:
        contigs = "{sample}/assembly/contigs.fasta"
    output:
        result = "{sample}/vpa/vpa_serotype.json"
```

输出 JSON 示例：
```json
{
  "sample": "RIMD2210633",
  "predicted_serotype": "O3:K6",
  "o_locus": "OL3",
  "o_confidence": "Perfect",
  "o_coverage": 100.0,
  "o_identity": 100.0,
  "o_missing_genes": "None",
  "o_alerts": "None",
  "k_locus": "KL6",
  "k_confidence": "Perfect",
  "k_coverage": 100.0,
  "k_identity": 99.98,
  "k_missing_genes": "None",
  "k_alerts": "None"
}
```

---

## MLST

- **Scheme**: PubMLST *V. parahaemolyticus*
- **Loci**: `dnaE`, `gyrB`, `recA`, `dtdS`, `pntA`, `pyrC`, `tnaA`
- **Tool**: `gmlst`

## AMR

- 使用 abricate（CARD / VFDB / PlasmidFinder）
- V. parahaemolyticus 临床株通常对多数抗生素敏感，AMR 基因相对少见
