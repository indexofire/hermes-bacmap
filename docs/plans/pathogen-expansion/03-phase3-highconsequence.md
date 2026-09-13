# P3 · 高后果/特殊病原：鼻疽与类鼻疽伯克霍尔德菌 + 艰难梭菌

前置：R0；建议 P1/P2 验收后启动 · 估算：8-10 人日 · 特征：**生物安全合规门禁**（伯克霍尔德）与厌氧菌场景

## 0. 生物安全前置（本期特有，最高优先级）

*B. mallei* 与 *B. pseudomallei* 属国家《病原微生物分类目录》高致病性病原（第一/二类），实验室操作需 BSL-3 与审批。**本平台仅处理测序数据（in silico），但必须**：

1. 注册表 `enabled: false` 默认关闭；启用需 config 显式开关 + `lint_pathogens.py` 强制确认
2. 两病原的任何分析事件（rule 触发、tool 调用、报告生成）写**审计日志**（复用 GOM events + review_flags 机制）
3. 报告卡片加生物安全声明栏（数据来源合规性由送检单位保证）
4. 文档明示：平台输出不构成病原体操作建议，仅序列分析

## 1. 类鼻疽伯克霍尔德菌（*B. pseudomallei*）+ 鼻疽伯克霍尔德菌（*B. mallei*)

**核心挑战**：B. mallei 是 B. pseudomallei 的克隆衍生种（基因组缩减 ~1.4 Mb），标志基因层面天然难分——这是与 Shigella/EIEC 同级但更难的鉴别问题，需要组合策略：

| 项 | 方案 | 依据 |
|---|---|---|
| 物种标志基因（复合群层） | TTS1 `orf2`（Bps 复合群确认，mallei 亦阳性） | 类鼻疽标准分子靶标 |
| **种间鉴别（mallei vs pseudomallei）** | 组合判定 `typing/burkholderia_discriminate.py`：<br>① 组装大小（mallei ~5.8 Mb vs pseudomallei ~7.2 Mb，assembly_stats 直接判）<br>② `bimA` 等位类型（Bm/Bp 变异位点 blast 判别）<br>③ ANI 面板（两物种代表株各 ≥5，skani 全库天然可分）<br>④ 标志基因缺失模式（mallei 缺 TTS1 部分区域）<br>→ deterministic 组合 verdict + confidence | 基因组缩减是稳定特征；多证据冗余 |
| MLST | PubMLST *B. pseudomallei* scheme（两物种共用，ST 互通） | 已核实 |
| cgMLST | cgmlst.org：**B. pseudomallei 专库（4221 loci）**、**B. mallei 专库（FLI 2838 / RKI 3328）**——按物种选库，vendor 通道获取 | 已核实三库存在 |
| 溯源阈值 | 无发表暴发阈值 → UNDETERMINED；华南地方性流行标注 | — |
| AMR | `--organism Burkholderia_pseudomallei` / `Burkholderia_mallei`（均已策展） | AMRFinderPlus 官方表 |
| SNP 参考 | Bps：K96243；Bm：NCTC 10229；分组独立 | 标准参考 |
| 近缘干扰 | *B. thailandensis/cepacia 复合群* 面板必含（类鼻疽环境假阳性经典来源） | — |
| gold standard | 各 ≥5 株（Bm 公开序列较少，可含参考株 + 公共数据） | — |

## 2. 艰难梭菌（*Clostridioides difficile*）

| 项 | 方案 | 依据 |
|---|---|---|
| 物种标志基因 | `tpi`（种确认）+ 毒力 `tcdA/tcdB`（产毒判定的充要证据）+ 二元毒素 `cdtA/cdtB` | 标准分子体系 |
| 毒素分型 | `typing/cdiff_toxin.py`：tcdA/tcdB/cdtA/cdtB 存缺 + `tcdC` 缺失（Δ117 等，RT027 特征）→ toxinotype 分组 verdict（产毒/非产毒/高毒力疑似 027 型） | WGS 判定体系 |
| 分型（ribotype → cgMLST 迁移） | **不实现 PCR ribotyping**（WGS 时代已证 cgMLST 更优）；MLST（PubMLST，ST-11=RT027 谱系高亮）+ **EnteroBase Cdiff cgMLST + HierCC**（1.8 万株背景库，本地参考库投影） | Baktash 2021 JCM：cgMLST 区分 82/100 RT；**暴发阈值 ≤3 allele（文献建议）** |
| 溯源阈值 | outbreak ≤3 allele（首个有发表支撑的新病原阈值）；related 沿 HierCC 分层策展 | Baktash 2021 |
| AMR | `--organism Clostridioides_difficile`（**四列全 X：获得性+突变+毒力+应激**，策展最全的病原之一） | AMRFinderPlus 官方表 |
| 厌氧/低 GC 适配 | GC ~29%：Shovill/pyrodigal 默认参数经 gold standard 验证；临床株常为培养物，覆盖度正常 | — |
| SNP 参考 | 630（RT012）/ R20291（RT027）双参考按谱系选择，或统一 NAP07?——实现期定；组 `cdifficile` | 标准参考 |
| gold standard | ≥10 株：RT027/RT078/RT014/非产毒株 | — |

公卫要点：RT027 检出（ST-11 + tcdC Δ117 + 二元毒素阳性）触发院感高优先级报告措辞；非产毒株（tcdA/tcdB 双阴）明确标注无临床意义。

## 3. 公共交付

1. 注册表 3 条目（伯克霍尔德 2 条 `enabled: false`）+ markers 扩展（~10 条序列）+ 面板 taxa（近缘：*B. thailandensis*、*B. cepacia* 复合群 2-3 株、非致病芽孢杆菌对照）
2. 新模块：`typing/burkholderia_discriminate.py`（多证据组合，本期技术核心）、`typing/cdiff_toxin.py`
3. cgMLST：vendor 脚本扩展伯克霍尔德三库 + EnteroBase Cdiff；`build_cgmlst_reference.py` 扩参考库
4. 生物安全门禁：config 开关 + 审计日志 + lint 强制确认 + 报告声明栏
5. skills references 3 篇 + `docs/pathogens/` 3 篇 + interpret-results 阈值文档（cdiff ≤3 首个新病原发表阈值）

## 4. 测试与验收

| 验收项 | 标准 |
|---|---|
| 单元测试 | burkholderia_discriminate 组合矩阵（大小/bimA/ANI/缺失四证据的全组合 + 冲突路径）≥12 测；cdiff_toxin 毒素模式 ≥8 测 |
| gold standard | Bps/Bm 种间鉴别 100%（各 ≥5 株）；近缘 *B. thailandensis* 不误判；cdiff 毒素判定 100%、ST-11→RT027 高亮正确 |
| 生物安全 | enabled=false 时样本表含该病原 → 管线拒绝 + 明确报错；启用后全事件审计可查 |
| 端到端 | cdiff ≥3 株全管线（伯克霍尔德用公共数据 ≥1 株演练审计链路） |
| cgMLST | cdiff cohort（≥3 株同 RT）距离矩阵 + ≤3 阈值判定正确 |

## 5. 风险

| 风险 | 缓解 |
|---|---|
| Bm 公开验证数据稀缺 | 参考株 + 仿真（Bps 基因组人工缩减不可行——以文献报道的公开 Bm 组装为准，数量约束写入 known-issues |
| 鉴别组合在混合/低质量组装上失稳 | 组装 N50/深度门槛检查 + 冲突时 NEEDS_REVIEW（不硬判） |
| 生物安全边界争议 | ADR 记录设计决策；报告措辞法务口径与送检单位确认 |
| EnteroBase Cdiff scheme 在 gmlst 的可用性 | 实现首日核实；备选 vendor 通道本地化 allele 库 |
