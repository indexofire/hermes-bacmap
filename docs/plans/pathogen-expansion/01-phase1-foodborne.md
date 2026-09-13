# P1 · 食源性/水源性病原：霍乱弧菌 + 单增李斯特菌 + 空肠/结肠弯曲菌

前置：R0 · 估算：10-12 人日 · 与现有 4 病原定位同构（食品/水传播监测），工具链最成熟

## 1. 霍乱弧菌（*Vibrio cholerae*）

| 项 | 方案 | 依据/来源 |
|---|---|---|
| 物种标志基因 | `toxR` + `ompW`（种确认）；产毒判定 `ctxA/ctxB` + `tcpA`；基因群 `rfbV/wbeT`（O1/O139） | 标准分子鉴定靶标；与 vpara 毒力 rule 同构 |
| 产毒/基因群模块 | 新 `typing/vcholerae_typing.py`：gene_scanner 扫描 → 三层判定（物种 / 产毒 / 基因群），输出 toxigenic O1/O139/非产毒等 verdict | 与 shigella_serotyper 委托模式同构 |
| MLST | PubMLST *V. cholerae* scheme（gmlst） | 已核实存在 |
| cgMLST | PubMLST cgMLST（2443 loci）或 EnteroBase Vibrio cgMLST+HierCC；gmlst scheme 名实现期用 `gmlst ls` 核实 | 已核实存在，名待验 |
| 溯源阈值 | 无发表值 → 默认 UNDETERMINED（沿 V.para 先例），阈值策展列为后续任务 | — |
| AMR | `--organism Vibrio_cholerae`（已策展，含点突变） | AMRFinderPlus 官方表 |
| SNP 参考 | N16961（O1 El Tor）；组 `vcholerae` | 标准参考 |
| gold standard | ≥10 株：O1 产毒/非产毒、O139、非 O1/O139 环境株（ENA/PubMLST 拉取） | — |

公卫要点（写入 interpret-results reference）：甲类传染病——产毒 O1/O139 检出应触发高优先级报告措辞；区分流行克隆（7PET）与本地非产毒株。

## 2. 单增李斯特菌（*Listeria monocytogenes*）

| 项 | 方案 | 依据/来源 |
|---|---|---|
| 物种标志基因 | `prs`（*Listeria* 属）+ `hly`（种，李斯特溶血素 O） | Doumith 体系基础 |
| 血清群 | **移植 LisSero 逻辑**（MDU-PHL，MIT/AGPL 注意核对——5 基因 lmo1118/lmo0737/ORF2110/ORF2819/Prs 组合 → 1/2a/1/2b/1/2c/4b 血清群）为新 `typing/lmono_serogroup.py`，gene_scanner 委托 | 与 ecoh_serotyper 完全同构（blast 扫描 + 组合判读），纯逻辑移植无许可争议 |
| MLST | PubMLST *L. monocytogenes* scheme | 已核实 |
| cgMLST | Pasteur/cgmlst.org Lm cgMLST（1701 loci，国际标准 CT 命名）；scheme 获取：`vendor_cgmlst_schemes.py` 扩展（EnteroBase **无** Listeria，需 cgmlst.org/Pasteur 通道） | cgmlst.org 已核实 1701 loci/25k CT |
| 溯源阈值 | Pasteur CT 相同 = 同克隆系；阈值策展任务（文献：cgMLST 差异 ≤7 视为近缘） | 待策展，先 UNDETERMINED |
| AMR | `--organism Listeria_monocytogenes`（已策展） | AMRFinderPlus 官方表 |
| SNP 参考 | EGDe；组 `listeria` | 标准参考 |
| gold standard | ≥10 株覆盖 4 主要血清群（1/2a、1/2b、1/2c、4b） | — |

公卫要点：暴发溯源是 Lm 的核心场景（国际标准即 cgMLST）——cohort 报告卡片需按 Pasteur CT 输出。

## 3. 空肠弯曲菌 + 结肠弯曲菌（*C. jejuni* / *C. coli*）

| 项 | 方案 | 依据/来源 |
|---|---|---|
| 物种标志基因 | jejuni：`mapA` + `hipO`；coli：`cdtA` + `ceuE`（两套 marker 同库，优先级 mapA/hipO > cdtA/ceuE） | 标准分子靶标 |
| 血清型 | **不实现**（Penner 血清分型在 WGS 时代已弃用）；毒力基因扫描（`cdtABC`、`iam`、`virB11` 等）走 abricate 自定义库 | PubMLST 实践 |
| MLST | PubMLST *C. jejuni/coli* **共用** scheme（campylobacter）——两物种同 scheme 分组同 cohort | 已核实（共用库） |
| cgMLST | cgmlst.org jejuni/coli cgMLST（637 loci）；scheme 获取同上扩展 | 已核实 637 loci |
| AMR | `--organism Campylobacter`（已策展，**含 gyrA T86I 点突变**——氟喹诺酮耐药主机制，AMRFinderPlus 直接输出）；红霉素耐药 ermB 走 abricate CARD | AMRFinderPlus 官方表 |
| SNP 参考 | jejuni：NCTC 11168；coli：RM2228；分两个 SNP 组 | 标准参考 |
| gold standard | ≥10 株两物种混合 | — |

公卫要点：弯曲菌是**全球最常见细菌性食源病**，AMR 监测（氟喹诺酮/大环内酯）与 MLST 聚类是主要输出；PubMLST 库自带基因型字段可作为校验参照。

## 4. 公共交付（本期 4 病原）

1. 注册表条目 + markers.fasta 扩展（`data/reference/species/`，8-10 条新序列，来源 GenBank 登录号记录入 manifest）
2. `typing/vcholerae_typing.py`、`typing/lmono_serogroup.py` 两个新模块（gene_scanner 委托模式，各 ~150 行 + 单测）
3. `rules/` 扩展：`vcholerae.smk`、`listeria.smk`、`campylobacter.smk`（沿 dec_shigella.smk 模式：rule 调 Python 模块 + fallback）
4. cgMLST：`vendor_cgmlst_schemes.py` 支持 cgmlst.org/Pasteur 通道；`build_cgmlst_reference.py` 扩展本地参考库（每病原 ≥30 株代表，NCBI Pathogen 目录 + RefSeq）
5. 物种鉴定面板（species-id A-mini）`taxa_filter.yaml` 加 4 物种 + 近缘（*V. mimicus/vulnificus*、*L. innocata/ivanovii/welshimeri* 等李斯特属近缘、*C. lari/upsaliensis*）
6. skills：`run-pipeline/references/` 增 3 篇病原操作指南；`interpret-results/references/` 增阈值与判读（沿 salmonella.md 模式）
7. `docs/pathogens/` 增 4 篇病原文档 + 总览矩阵更新

## 5. 测试与验收

| 验收项 | 标准 |
|---|---|
| 单元测试 | 两个新 typing 模块各 ≥10 测（组合判读矩阵全覆盖，含 fallback） |
| gold standard | 4 病原物种鉴定 ≥99%；Lm 血清群 ≥95%；V. cholerae 产毒/基因群 100%；弯曲菌 MLST ST 与 PubMLST 一致 ≥99% |
| AMR | 弯曲菌 gyrA T86I 检出与表型一致率报告（≥95%）；其余病原获得性基因 vs abricate 交叉验证 |
| 端到端 | 每病原 ≥3 株 FASTQ 全管线跑通，summary.json / GOM / 报告卡片完整 |
| DAG | 15 病原混合样本表（含本期 4）dry-run：SNP/cgMLST 分组正确（jejuni 与 coli 分组、弯曲菌与李斯特各自成 cohort） |

## 6. 风险

| 风险 | 缓解 |
|---|---|
| gmlst 对新 scheme 名/等位库支持差异 | 实现首日用 `gmlst ls` 全量核实；不支持者走 vendor 脚本本地化 |
| Lm cgMLST 无 EnteroBase 通道 | vendor_cgmlst_schemes.py 扩 cgmlst.org/Pasteur 下载（allele FASTA → 本地索引） |
| V. cholerae 近缘（*V. mimicus*）标志基因交叉反应 | 面板含近缘株 + marker 阈值保守 + gold standard 含近缘阴性对照 |
| LisSero 逻辑移植的许可 | 仅移植基因组合判定表（科学事实），代码独立实现；LICENSE 审查记录入 ADR |
