# 分层物种鉴定体系

Hermes-bacmap 采用**分层鉴定**架构：多方法并存、统一切换、跨方法仲裁。物种鉴定回答"**是什么物种**"，与分型模块（毒力/血清型/耐药，回答"**有多危险**"）互补，不冗余。

## 架构总览

```
用户 / AI 对话
    ↓
species_mode 统一切换（config.yaml / CLI / 对话工具）
    ↓
┌─────────────────────────────────────────────────────────────────┐
│                     分层鉴定方法                                  │
│                                                                 │
│  Layer 1 · marker 靶基因（multigene_identifier.py）              │
│  ├─ 80 个靶标基因 / 38 条判定规则 / 34 种病原                     │
│  ├─ 秒级 / 0 额外数据库 / species_mode=simple                    │
│  └─ 适用：快速初筛、常规监测                                      │
│                                                                 │
│  Layer 2 · ANI 全基因组比对                                       │
│  ├─ skani 精选面板（284 株 / 125 MB）   → species_mode=panel      │
│  ├─ Mash RefSeq sketch（159 MB）       → species_mode=mash_refseq │
│  ├─ skani GTDB 全库（30 GB）           → species_mode=skani_gtdb  │
│  └─ 适用：确认鉴定、近缘种区分                                    │
│                                                                 │
│  Layer 3 · 混合样本分解                                           │
│  ├─ sourmash gather（3.7 GB）          → species_mode=sourmash    │
│  └─ 独特价值：最小集合覆盖分解，检测混合样本/污染                   │
│                                                                 │
│  Layer 4 · 金标准仲裁                                             │
│  ├─ GTDB-Tk + CheckM2（98 GB + 140 GB RAM）→ species_mode=standard│
│  └─ 适用：争议仲裁、监管复核、新物种鉴定                            │
│                                                                 │
│  Layer 0 · reads 级预筛（正交开关）                                │
│  ├─ Kraken2 自建库                    → kraken2_prefilter=true     │
│  └─ 组装前污染/混合告警 + 去人源（合规）                           │
└─────────────────────────────────────────────────────────────────┘
    ↓
species_consensus（跨方法仲裁）
    ↓
Deterministic Verifier（Layer 2 防御）
    ↓
GOM ANALYSIS 对象（Immutable，多方法并存）
    ↓
bio_species_compare tool（一致性矩阵 + 仲裁结论 + NEEDS_REVIEW）
    ↓
LLM 解读（skill 引导，只做"意味着什么"的解读）
```

## 分层方法详解

### Layer 1: marker 靶基因鉴定（`multigene_identifier.py`）

| 项 | 值 |
|---|---|
| 数据库 | `markers_v2` BLAST DB（80 条序列 / 108,808 bp） |
| 判定规则 | `marker_rules.yaml`（38 条，覆盖 34 种病原） |
| 耗时 | 每株秒级 |
| 额外存储 | 0 |
| 切换 | `species_mode=simple`（默认） |

#### 多基因组合判定原理

单基因鉴定有已知局限（交叉反应、种内同源），本项目采用**多基因组合**提高准确性：

| 鉴别难题 | 单基因缺陷 | 组合规则 | 来源 |
|---|---|---|---|
| E. coli vs Shigella | uidA 在 Shigella 中 44% 阳性 | uidA + lacY + gadA ≥2 个命中 → DEC；ipaH(+)+lacY(-) → Shigella | [FDA BAM Ch.4](https://www.fda.gov/media/183681/download) |
| V. para vs V. alginolyticus | tlh 交叉反应（85.2%） | toxR ≥90% + tlh ≥90% → V.para；tlh 单独 <90% 抑制判定 | 本项目验证 |
| C. jejuni vs C. coli | 单基因假阴性 | mapA(+) → jejuni；ceuE(+) → coli | [Linton et al. 1997](https://doi.org/10.1128/jcm.35.11.2568-2572.1997) |
| L. mono vs L. innocua | 表型不可区分 | prs(+) + hly(+) → L. mono；prs(+) hly(-) → 非致病 | [Doumith et al. 2004](https://doi.org/10.1128/JCM.42.8.3819-3822.2004) |
| B. anthracis vs B. cereus | 16S 无法区分 | pagA + capB 双阳性 → B. anthracis | [CDC](https://www.cdc.gov/anthrax/) |
| 产毒 vs 非产毒 V. cholerae | 物种鉴定不区分毒性 | ompW(+) + ctxA(+) → 产毒株（甲类） | [Nandi et al. 2000](https://doi.org/10.1128/JCM.38.11.4145-4151.2000) |

#### 已知交叉反应防护

| 基因 | 交叉物种 | 交叉率 | 防护机制 |
|---|---|---|---|
| tlh | V. alginolyticus | ~85% identity | 近缘守卫：单独 <90% 不判定 |
| uidA | Shigella (44%), Salmonella (29%) | ~80-85% | 不能单独判定，需组合 |
| eae | Citrobacter, E. albertii | ~85% | 需结合 stx + 血清型 |
| 16S rRNA | 种内多拷贝异质 | ~99%+ | 不用于种级鉴定 |

### Layer 2: ANI 全基因组比对

#### skani 精选面板（`species_mode=panel`）

| 项 | 值 |
|---|---|
| 数据库 | 284 株精选临床病原（Complete Genome / N<500 / 无克隆冗余） |
| 覆盖 | 72 种临床重要病原 + 近缘对照 |
| skani 库 | 125 MB（markers.bin + sketches.db + index.db） |
| 耗时 | 毫秒级/株 |
| 阈值 | ANI ≥95% + AF ≥0.65 → high；93-95% → medium（边界区） |

**精选面板构建流程**：

```
NCBI Pathogen Detection 追踪清单（106 组）
    ↓ 三轮噬菌体清除（839 株）+ N>1000 清除（28 株）
    ↓ 临床重要性分级（T1-T4）→ 配额 2-10 株/物种
    ↓ 种内克隆去除（ANI ≥99.99% 的冗余删除）
    ↓ 284 株最终面板
```

#### Mash RefSeq sketch（`species_mode=mash_refseq`）

| 项 | 值 |
|---|---|
| 数据库 | Zenodo 社区维护（159 MB，随 RefSeq 自动更新） |
| 耗时 | 秒级/株 |
| 阈值 | identity ≥0.97 → high；0.90-0.97 → medium |
| 验证 | 17/17 (100%) |

#### skani GTDB 全库（`species_mode=skani_gtdb`）

| 项 | 值 |
|---|---|
| 数据库 | 官方预 sketch GTDB R226（>14 万物种代表株） |
| 下载 | 30 GB 压缩 / 50 GB 解压 |
| 查询 RAM | <30 GB |
| 耗时 | 毫秒级/株 |
| 适用 | 广谱真 ANI（任意细菌物种） |

### Layer 3: sourmash gather（`species_mode=sourmash`）

| 项 | 值 |
|---|---|
| 数据库 | sourmash GTDB RS226 签名（3.7 GB） |
| 耗时 | 秒级/株 |
| 独特价值 | **最小集合覆盖分解**（检测混合样本/污染） |

**混合样本判定**：gather 分解出 ≥2 个不同属的组分且各自 containment ≥10% → `possible_mixture` flag，触发 NEEDS_REVIEW。

### Layer 4: GTDB-Tk + CheckM2（`species_mode=standard`）

| 项 | 值 |
|---|---|
| GTDB-Tk | v2.7.2 + R232 数据库（98 GB） |
| CheckM2 | v1.1.0 + DIAMOND 库（3 GB） |
| RAM 硬门禁 | ≥140 GB（不足时下载脚本拒绝） |
| 耗时 | 分钟-小时级 |
| 定位 | 金标准仲裁（争议/监管/新物种） |

### Layer 0: Kraken2 reads 级预筛（独立开关）

| 项 | 值 |
|---|---|
| 数据库 | 自建（精选面板 + GRCh38 + UniVec，~5 GB） |
| 输入 | 原始 reads（组装前） |
| 耗时 | 分钟级 |
| 价值 | 污染/混合最早告警 + 人源序列剔除（合规） |

## 跨方法仲裁（species_consensus）

### 优先级规则

```
gtdbtk (Layer 4) > {skani_gtdb, panel, sourmash, mash_refseq} (Layer 2/3) > marker (Layer 1)
```

| 冲突类型 | 处理 | 示例 |
|---|---|---|
| 高层 vs 低层不一致 | 高层覆盖低层，记录冲突但不否决 | GTDB-Tk 说 Listeria，marker 说 Unknown → Listeria |
| **同层**方法冲突 | `NEEDS_REVIEW`（人工裁决） | skani 说 Salmonella，mash 说 Vibrio → NEEDS_REVIEW |
| Shigella/EIEC ↔ E. coli | `expected_divergence`（同种，不触发人审） | 生物学已知，GTDB 合并处理 |

### 输出

`bio_species_compare` tool 一致性矩阵：

```
菌株 SAM-TYP-001 — 物种鉴定方法对比
method       species         confidence
marker       Salmonella      high
panel        Salmonella      high
结论: Salmonella (agreement=match, basis=panel)
```

如需人审：
```
⚠ NEEDS_REVIEW: 同层方法冲突，需人工裁决
分歧方法: skani_gtdb, sourmash
```

## GOM 证据链

每种方法的每次鉴定 = 独立 ANALYSIS 对象（Immutable, INSERT-ONLY）：

```json
{
  "analysis_type": "species_identification",
  "method": "multigene",
  "database": {"name": "markers_v2", "version": "abc12345"},
  "result": {
    "species": "Salmonella",
    "confidence": "high",
    "detected_markers": [{"gene": "invA", "identity": 99.8}]
  }
}
```

多方法并存：同一株样本可以有 marker / panel / mash / GTDB-Tk 多个对象，`bio_species_compare` 聚合输出仲裁结论。

## 统一选择面

| 入口 | 命令 |
|---|---|
| config.yaml | `species_mode: simple \| panel \| skani_gtdb \| mash_refseq \| sourmash \| standard` |
| CLI | `run_analysis.py --species-mode panel` |
| 对话 | `bio_db_setup`（选档部署）+ `bio_species_compare`（查矩阵） |
| 部署 | `pixi run setup` 或 `scripts/setup_databases.py --tier mini` |

**缺库自动降级**：任何模式的数据库缺失 → WARNING + 回退 marker-only，不中断管线。

## 方法选择建议

| 场景 | 推荐方法 | 理由 |
|---|---|---|
| 日常监测（快速初筛） | `simple`（multigene） | 秒级、零开销 |
| 常规分析（确认鉴定） | `panel`（skani 面板） | 秒级真 ANI，125 MB |
| 快速预筛（低配置机器） | `mash_refseq` | 159 MB 即覆盖全 RefSeq |
| 广谱鉴定（非目标病原） | `skani_gtdb` | >14 万物种全覆盖 |
| 混合样本排查 | `sourmash` | gather 分解 |
| 争议仲裁 / 监管复核 | `standard`（GTDB-Tk） | 金标准 |
| 组装前污染检查 | `kraken2_prefilter` | 最早告警 + 去人源 |

## 验证状态

| 方法 | 验证集 | 准确率 | 已知局限 |
|---|---|---|---|
| multigene | 17 株（7 目标 + 10 近缘阴性对照） | **17/17 (100%)** | C. jejuni/coli 标记待修复 |
| skani panel | 17 株 | **17/17 (100%)** | 面板覆盖 72 种 |
| mash_refseq | 17 株 | **17/17 (100%)** | MinHash 近似 |
| skani_gtdb | 未下载 | — | 30 GB |
| sourmash | 未下载 | — | 3.7 GB |
| GTDB-Tk | 未下载 | — | 需 140 GB RAM |

## 参考文献

- Jain C, Rodriguez-R LM, Phillippy AM, et al. High throughput ANI analysis of 90K prokaryotic genomes reveals clear species boundaries. *Nat Commun*. 2018;9:5114.
- Shaw J, Yu YW. Fast and robust metagenomic sequence comparison through sparse chaining with skani. *Nat Methods*. 2023;20:1661-1665.
- Chaumeil PA, Mussig AJ, Hugenholtz P, Parks DH. GTDB-Tk v2: memory friendly classification with the Genome Taxonomy Database. *Bioinformatics*. 2022;38(23):5315-5316.
- Pierce NT, Irber L, Reiter T, et al. Large-scale sequence comparisons with sourmash. *F1000Res*. 2019;8:1006.
- Wood DE, Lu J, Langmead B. Improved metagenomic analysis with Kraken 2. *Genome Biol*. 2019;20(1):257.
- Barbau-Piednoir E, et al. SYBR Green qPCR Salmonella detection system. *Appl Microbiol Biotechnol*. 2013;97(12):5271-5279.
- Botteldoorn N, et al. Evaluation of multiplex PCRs for diagnosis of infection with diarrheagenic E. coli and Shigella spp. *J Clin Microbiol*. 2004;42(12):5849-5853.
