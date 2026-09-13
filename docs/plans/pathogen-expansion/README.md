# 病原扩展开发计划（V0.9 专项：4 → 15 病原）

状态：计划评审中 · 起草日期：2026-09-12 · 前置：物种鉴定多方法体系（`docs/plans/species-id/`）建议先行或并行

在现有 4 病原（沙门菌、DEC、志贺菌、副溶血性弧菌）基础上扩展 11 种常见病原。所有工具与 scheme 可用性均已核实（2026-09 检索官方来源）。

## 新增病原清单

| # | 病原 | 中文名 | 公卫场景 | 分期 |
|---|---|---|---|---|
| 1 | *Vibrio cholerae* | 霍乱弧菌 | 甲类传染病，水/食源 | P1 |
| 2 | *Listeria monocytogenes* | 单增李斯特菌 | 严重食源感染，高危人群致死率高 | P1 |
| 3 | *Campylobacter jejuni* | 空肠弯曲菌 | 全球最常见细菌性食源病 | P1 |
| 4 | *Campylobacter coli* | 结肠弯曲菌 | 同上，常混检 | P1（与 3 同组） |
| 5 | *Streptococcus pneumoniae* | 肺炎链球菌 | 疫苗时代血清型监测 | P2 |
| 6 | *Neisseria meningitidis* | 脑膜炎奈瑟菌 | 流脑，疫苗抗原监测 | P2 |
| 7 | *Legionella pneumophila* | 嗜肺军团菌 | 冷却塔/医院内暴发调查 | P2 |
| 8 | *Mycoplasma pneumoniae* | 肺炎支原体 | 儿童呼吸道流行，大环内酯耐药 | P2 |
| 9 | *Burkholderia pseudomallei* | 类鼻疽伯克霍尔德菌 | 类鼻疽（华南地方性），高致病 | P3 |
| 10 | *Burkholderia mallei* | 鼻疽伯克霍尔德菌 | 鼻疽（罕见人畜共患），管制病原 | P3 |
| 11 | *Clostridioides difficile* | 艰难梭菌 | 抗生素相关腹泻，院感监测 | P3 |

## 已核实的能力矩阵（检索自官方来源，2026-09）

| 病原 | MLST | cgMLST | 血清型/分型工具 | AMRFinderPlus 策展 |
|---|---|---|---|---|
| V. cholerae | PubMLST 有 | PubMLST cgMLST（2443 loci）+ **EnteroBase Vibrio cgMLST+HierCC**（2.7 万株） | 基因群（O1/O139）+ 毒力（ctxAB/tcpA）基因扫描 | ✅（含点突变） |
| L. monocytogenes | PubMLST 有 | cgmlst.org **Lm cgMLST（1701 loci）**，Pasteur 体系国际标准 | **LisSero**（MDU-PHL，5 基因血清群 1/2a/1/2b/1/2c/4b，blast 模式） | ✅（获得性+突变） |
| C. jejuni / C. coli | PubMLST（共用库，含 AMR 基因型字段） | cgmlst.org **jejuni/coli cgMLST（637 loci）** + PubMLST cgMLST v2 | 无常规血清型（Penner 已弃用）→ MLST/毒力基因 | ✅ **Campylobacter（含 gyrA 点突变）** |
| S. pneumoniae | PubMLST 有 | cgmlst.org 有 | **SeroBA**（Sanger，k-mer reads 级，98% 一致率）/ PneumoCaT（UKHSA，CTV 库 92+ 型） | ✅（**含分歧 PBP 检测**） |
| N. meningitidis | PubMLST 有 | PubMLST cgMLST 有 | **meningotype**（MDU-PHL：血清群 + MLST + porA/fetA/porB finetype + BAST 疫苗抗原 + MenDeVAR 指数） | ✅（获得性+突变+毒力） |
| L. pneumophila | SBT（7 基因） | PubMLST 有 | **legsta**（T. Seemann，in silico SBT） | ✅（获得性） |
| M. pneumoniae | PubMLST 有 | 少用 | P1 基因分型（无血清型） | ❌ **唯一缺失**——23S rRNA A2063G 大环内酯耐药需自研点突变调用 |
| B. pseudomallei | PubMLST 有 | cgmlst.org **Bps cgMLST（4221 loci）** | 无血清型；MLST + WGS | ✅（获得性+突变+毒力） |
| B. mallei | 与 Bps 共用困难 | cgmlst.org **Bm 专库（FLI 2838 / RKI 3328 loci）** | **与类鼻疽近同种**（克隆衍生），标志基因难分 → ANI + 基因组大小/结构鉴别 | ✅ |
| C. difficile | PubMLST 有（毒力/核糖体分型字段） | **EnteroBase Cdiff cgMLST+HierCC**（1.8 万株） | PCR ribotyping → WGS 时代建议迁 cgMLST（文献：cgMLST 区分 82/100 RT；**暴发阈值建议 ≤3 allele**） | ✅（获得性+突变+毒力+应激） |

**两个关键结论**：

1. **AMR 层几乎零成本**：10/11 病原已被 AMRFinderPlus 官方策展（含点突变库，S. pneumoniae 有专门 PBP 检测），现有 `amr_amrfinderplus` rule 只需扩展 `_AMRFINDER_ORGANISMS` 映射。唯一缺口是肺炎支原体（23S 突变自研）。
2. **分型工具与我们现有架构同构**：LisSero/meningotype 均为 blast 基因扫描 + 组合判读，与 `ecoh_serotyper`/`shigella_serotyper` 的 gene_scanner 委托模式一致，移植成本低；SeroBA 例外（reads 级 k-mer，需新输入形态）。

## 架构瓶颈与 R0 重构（必做前置）

当前 4 病原配置散落在 **6+ 处硬编码字典**：

- `analysis/species_identifier.py` → `_GENE_TO_SPECIES`
- `rules/typing_amr.smk` → `_GMLST_SCHEMES`、`_AMRFINDER_ORGANISMS`
- `rules/snp.smk` → `_SPECIES_GROUPS`
- `rules/cgmlst.smk` → `_CGMLST_SCHEMES`
- samples.tsv species 枚举与 skills 文档

扩到 15 病原前必须收敛为**单一病原注册表** `workflows/bacmap/config/pathogens.yaml`，全部 rule/模块表驱动读表。
详见 [00-registry.md](00-registry.md)。

## 分期路线

| 期 | 文档 | 内容 | 定位逻辑 | 估算 |
|---|---|---|---|---|
| R0 | [00-registry.md](00-registry.md) | 注册表重构 + 4 病原迁移（行为不变） | 架构前置 | 4 人日 |
| P1 | [01-phase1-foodborne.md](01-phase1-foodborne.md) | V. cholerae + L. monocytogenes + C. jejuni/coli（4 种） | 食源性/水源性，与现有定位同构，工具链最成熟 | 10-12 人日 |
| P2 | [02-phase2-respiratory.md](02-phase2-respiratory.md) | S. pneumoniae + N. meningitidis + L. pneumophila + M. pneumoniae | 呼吸道，引入 reads 级分型（SeroBA）与自研点突变 AMR（Mpn） | 12-15 人日 |
| P3 | [03-phase3-highconsequence.md](03-phase3-highconsequence.md) | B. mallei/pseudomallei + C. difficile | 高后果/管制病原（生物安全门禁）+ 厌氧菌 | 8-10 人日 |

总量约 **35-40 人日**。依赖关系：R0 → P1 → P2 → P3（P2/P3 可在 P1 验收后并行）；与物种鉴定专项共用 `pathogens.yaml`（marker 注册与 A-mini 面板 taxa_filter 均从注册表生成）。

## 每病原统一交付清单（模板，各期细化）

每病原统一交付：物种标志基因（markers.fasta + 注册表）、MLST scheme 映射、血清型/分型模块（新 `typing/` 模块或外引工具）、AMRFinderPlus organism 映射、SNP 参考基因组与分组。
另含：cgMLST scheme 与溯源阈值（无发表阈值者按 V.para 先例置 UNDETERMINED）、物种鉴定面板 taxa 扩展、gold standard 验证株 ≥10 株、GOM `database_versions` 与 skill 参考文档（interpret-results references）。

## 总验收标准

1. 任一期病原：FASTQ 进 → summary.json 出，全链无手工干预；GOM 对象含全部新分析类型
2. `pathogens.yaml` 单点增删病原 = 全部 rule/模式自动跟随（R0 验收核心：加一个 stub 病原不改任何 .smk）
3. gold standard 验证：各病原物种鉴定/MLST/分型准确率 ≥ 项目 §12.3 现行指标
4. 15 病原混合样本表下 Snakemake DAG 正确分组（SNP/cgMLST cohort 各自成组）
5. P3 病原默认关闭，启用需显式配置 + 审计日志（生物安全合规）
