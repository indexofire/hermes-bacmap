# P2 · 呼吸道病原：肺炎链球菌 + 脑膜炎奈瑟菌 + 嗜肺军团菌 + 肺炎支原体

前置：R0（P1 建议先行但非硬依赖） · 估算：12-15 人日 · 引入两项新能力形态：reads 级分型工具（SeroBA）与自研点突变 AMR（肺炎支原体）

## 1. 肺炎链球菌（*Streptococcus pneumoniae*）

| 项 | 方案 | 依据/来源 |
|---|---|---|
| 物种标志基因 | `lytA`（自溶素，种特异金标准）+ `ply`（肺炎溶血素） | 标准 molecular 靶标 |
| 血清型（92+ 型） | **主方案：外引 SeroBA**（Sanger；k-mer reads 级；对 Quelling 一致率 98%；CTV 库内置含 6E/23B1 等）——pixi 依赖 `kmc` + `ariba` | Epping 2018 Microb Genomics |
| 血清型备选 | 组装级 blast 对 CTV `reference.fasta`（92 型 cps locus）——与 ecoh 同构可快速原型，但发表验证的是 reads 级；仅作降级路径 | CTV 库结构支持 |
| MLST | PubMLST *S. pneumoniae* scheme | 已核实 |
| cgMLST | cgmlst.org S. pneumoniae cgMLST（vendor 通道） | 已核实存在 |
| AMR | `--organism Streptococcus_pneumoniae`——**含分歧 PBP 蛋白检测**（青霉素耐药核心机制 pbp1a/2x/2b） | AMRFinderPlus 官方表（专门标注此能力） |
| 疫苗覆盖注释 | interpret 层：血清型 → PCV13/PCV20/PPSV23 覆盖映射（静态表，非分析） | 公卫监测刚需 |
| SNP 参考 | ATCC 700669（或 D39）；组 `spneumoniae` | 标准参考 |
| gold standard | ≥10 株覆盖常见血清型（19A、6A、23F、14、3、VT 与非疫苗型） | GPS 项目数据可得 |

新形态工作：`rules/seroba.smk`——**reads 输入**（qc 后 clean reads）的 rule，输出 pred.tsv 解析为 JSON。这是管线中第一个 reads 级分型步骤，rule 模式可复用给未来同类工具。

## 2. 脑膜炎奈瑟菌（*Neisseria meningitidis*）

| 项 | 方案 | 依据/来源 |
|---|---|---|
| 物种标志基因 | `ctrA`（荚膜转运，种确认）+ `sodC`（与淋病奈瑟菌鉴别的标准靶标） | Mothershed 2004 体系 |
| 分型 | **外引 meningotype**（MDU-PHL，Python+blast）：血清群（genogroup B/C/Y/W/X/A/csnull）+ porA/fetA VR finetype + porB + **BAST 疫苗抗原**（fHbp/NHBA/NadA/PorA）+ MenDeVAR 指数 | 已核实，功能完整度最高 |
| 等位库 | `meningotype --updatedb` 从 PubMLST 拉取 → 下载脚本化（版本入 manifest） | 工具原生支持 |
| MLST | PubMLST *N. meningitidis* scheme（工具 --mlst 一并输出） | 已核实 |
| cgMLST | PubMLST ntns/cgMLST scheme；gmlst 支持度实现期核实，不则 meningotype 生态内解决 | 待验 |
| AMR | `--organism Neisseria_meningitidis`（已策展：获得性+突变+毒力；penA 插入突变→青霉素敏感下降） | AMRFinderPlus 官方表 |
| SNP 参考 | MC58（serogroup B）；组 `nmeningitidis` | 标准参考 |
| gold standard | ≥10 株覆盖主要血清群（B/C/Y/W）+ csnull | PubMLST 公开数据 |

公卫要点：csnull（荚膜缺失株，青霉素/疫苗逃逸相关）必须显式判读；MenDeVAR 指数直接服务 Bexsero/Trumenba 疫苗抗原匹配报告。

## 3. 嗜肺军团菌（*Legionella pneumophila*）

| 项 | 方案 | 依据/来源 |
|---|---|---|
| 物种标志基因 | `mip`（属级共识基因，种确认）+ SG1 特异标记（`wzm`） | EWGLI 体系 |
| 分型 | **移植 SBT 7 基因等位分型**（flaA/pilE/asd/mip/mompS/proA/neuA）为 `typing/legionella_sbt.py`：gene_scanner 精确等位匹配（blast → 100% identity 对 allele 库）→ ST | legsta 同逻辑；allele FASTA 从 PubMLST 下载（下载脚本 + 版本入 manifest） |
| MLST | SBT 即 MLST（同 scheme） | — |
| cgMLST | 不启用（SBT + SNP 是军团菌主流溯源方式） | — |
| AMR | `--organism Legionella_pneumophila`（获得性基因） | AMRFinderPlus 官方表 |
| SNP 参考 | Philadelphia-1（或 Paris）；组 `lpneumophila` | 标准参考；冷却塔暴发调查以 SNP 为主 |
| gold standard | ≥10 株含 SG1 与非 SG1、已知 ST | EWGLI/PubMLST |

## 4. 肺炎支原体（*Mycoplasma pneumoniae*）

| 项 | 方案 | 依据/来源 |
|---|---|---|
| 物种标志基因 | P1 黏附素 `mpn141` + CARDS 毒素 `mpn372` | 种特异金标准靶标 |
| 分型 | P1 基因型（1/2/6 型，`mpn141` repMP2/3 同源区组合）+ MLST（PubMLST scheme） | 文献体系 |
| **AMR（本病原核心）** | **自研点突变模块 `typing/mpn_amr.py`**：23S rRNA `A2063G/A2067G`（大环内酯耐药，bla/四环素类不适用——无细胞壁）→ 从 contigs blast 提取 23S → 等位比对突变位点 → 耐药 verdict（含基因型-表型对应表） | **AMRFinderPlus 唯一未策展的病原**，自研是必然 |
| AMR 补充 | abricate CARD 照跑（获得性 tetM 等） | — |
| 小基因组适配 | 基因组 0.8 Mb / GC 40% / 培养困难覆盖度低 → fastp/组装参数经注册表 per-pathogen 覆盖验证（Shovill 默认预计可用，gold standard 实测确认） | — |
| SNP 参考 | M129（ATCC 29342）；组 `mpneumoniae` | 标准参考 |
| cgMLST | 不启用 | — |
| gold standard | ≥10 株含大环内酯敏感/耐药（2063G/2067G 各若干） | — |

公卫要点：中国儿童 Mpn 大环内酯耐药率 >80%（地域差异大）——突变检测是该病原监测的**第一输出**，报告卡片需突出显示。

## 5. 公共交付

1. 注册表 4 条目 + markers 扩展（8 条序列）+ 面板 taxa（近缘：*S. mitis/pseudopneumoniae*（**口咽共生高混淆源**，必须阴性对照）、*N. gonorrhoeae/lactamica*、非 LP 军团菌 2-3 种、*M. genitalium*）
2. 新模块：`typing/legionella_sbt.py`、`typing/mpn_amr.py`、`typing/mpn_p1.py`（gene_scanner 模式）
3. 外引工具：SeroBA（pixi：kmc、ariba）+ meningotype（pixi pypi）+ 两者 rule 与 JSON 解析脚本
4. 等位库下载脚本 2 个（meningotype DB、军团菌 SBT allele FASTA）——纳入 species-id 下载框架同规范（manifest/校验/幂等）
5. skills references 4 篇 + `docs/pathogens/` 4 篇
6. reads 级分型 rule 模式沉淀为文档（`architecture/pipeline.md` 增补）

## 6. 测试与验收

| 验收项 | 标准 |
|---|---|
| gold standard | 4 病原物种鉴定 ≥99%；SeroBA 血清型 vs Quellung/参考 ≥95%；meningotype 血清群 100%、porA/fetA 与 PubMLST 一致 ≥99%；军团菌 SBT ST 100%；Mpn 23S 突变检测 100%（敏感/耐药株） |
| S. mitis 阴性对照 | ≥3 株口腔链球菌不误判为肺炎链球菌（标志基因 + ANI 双层验证） |
| AMR | Mpn 突变模块与 Sanger/参考株基因型一致；其余病原 AMRFinderPlus 输出与 abricate 交叉验证 |
| 端到端 | 每病原 ≥3 株全管线 + GOM + 报告卡片；SeroBA 链路 reads 输入正确（qc 后 clean reads） |
| 注册表扩展 | 4 条目 lint 通过；15 病原混合 dry-run 分组正确 |

## 7. 风险

| 风险 | 缓解 |
|---|---|
| SeroBA 依赖链重（kmc/ariba） | pixi 独立 feature 环境 `serotyping`；降级路径：CTV 组装级 blast |
| *S. mitis* 交叉（肺炎链球菌鉴定的经典坑） | marker 层保守 + ANI 面板含共生链球菌 + gold standard 阴性对照（三层防） |
| meningotype PubMLST 库拉取限流 | 下载脚本缓存 + manifest 版本固定 + 重试 |
| Mpn 低覆盖样本 23S 覆盖不足 | 模块输出覆盖度警告（<20x 突变判读不可靠→NEEDS_REVIEW） |
| 支原体无细胞壁 AMR 语义混淆 | interpret reference 明确：β-内酰胺类结果对 Mpn 无意义，报告层过滤 |
