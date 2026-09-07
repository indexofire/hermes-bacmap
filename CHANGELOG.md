# Changelog

All notable changes to hermes-bacmap are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed — 评审 P0 修复：NLI Reflector 语义缺陷 + 验证报告口径 + 文档门禁（2026-09-08）

- **A1 否定盲区**：`decompose_claims` 增加否定窗口检测（中/英标记 + 间隙约束，防「非常罕见」类误报），
  `AtomicClaim` 增 `negated` 字段，比对语义改为 ENTAILED iff (匹配 != negated)——「不是沙门菌，而是志贺菌」
  在志贺株上不再误报人审；「未检出 X」在携带株上正确判 CONTRADICTED、阴性株判 ENTAILED；
  佐证回填支持否定式提及（文本否认管线检出基因 → 矛盾 verdict，不进分母）
- **A2 基因身份归一共享**：新建 `analysis/gene_identity.py`（`normalize_amr`：bla 前缀 + mcr 变体），
  nli_reflector 与 validate_analytical 共用同一实现——「检出 blaCTX-M-15」vs facts `CTX-M-15`
  不再假矛盾（原同一 PR 内两模块对基因身份判定不一致）
- **A3 分母稀释**：`contradiction_rate` 只对 decomposed（文本提取）claims 计算；佐证回填单列
  `corroborated_count`（layer3 响应同步输出）——单条矛盾 ST 不再被 ~15 条佐证基因淹没
  （原 1/16 < 0.1 漏报路径修复）
- **A4 验证报告口径**：`MetricsReport` 增 `amr_precision_tp/fp`，precision 行显示与 percentage 同口径的
  子集值，合并 TP/FP 移至括注——§12.3 审计数字可复现
- **B 文档门禁与计数**：CHANGELOG/features.md 两处 >200 字符行折行（原 pre-commit CI 必红）；
  测试计数统一至 **1389**（README/docs/index/known-issues/project.md 此前停在 1316）；README 与 features
  正文的 schemas 行（893 行/25 个）及图示 tools/rules 计数对齐
- 测试 1376 → **1389**（+13：否定语义 7 / 归一共享 3 / 稀释回归 2 / 精确度口径 1）

### Added — V0.7 Wave 3 扩充：ECO-011/MCR-010 补跑 + 三项数据/管线修复（2026-09-07）

- **samples.tsv 10 → 12**：SAM-ECO-011（E. coli K-12 MG1655 阴性对照）与 SAM-MCR-010（mcr-1）登记并补跑全管线
- **MCR-010 R2 FASTQ 修复**：aria2c 8 线程断点续传重下（ENA ERR2594882_2），MD5 与 ENA 报告值一致
  （`8f4dec30...`），gzip -t 通过——关闭 V0.2 遗留的"R2 下载损坏待修复"
- **修复 species_markers BLAST 索引缺失**（known-issues B3）：f-string 修复后的 species_identify
  首次真实执行即 FileNotFoundError，重建索引后 ECO-011 uidA 100%/100% → DEC 路由正确
- **修复 fallback 无效 JSON**（known-issues B3）：4 处 `'|| echo'` 兜底参数 `{{...}}` 改单花括号
  ——mini-Snakefile 实证 snakemake 7.32 对 params 值原样透传，原双花括号转义假设自引入即错误
- **harness 测量学完善**：N/A 期望 ST 跳过（"N/A (K-12 reference)" 无比较意义）；mcr 等位变异归一
  （MCR-1.1 ≡ mcr-1，跨家族不归一）；FN/FP 清单按 170 字符预算截断（MD013 契约，完整数据在 metrics.json）
- **9 株终测**：物种 **100%**（含 ECO-011 阴性对照正确分流）、血清型 **100%**、AMR 灵敏度 **100%**
  （TP=92 FN=0）、MLST **85.7%**——MCR-010 判 ST19 vs gold 期望 ST34（gold alleles 为 PENDING 未验证值），
  如实呈现（docs/validation-report.md Strain-specific findings）。后续文献核实（Sia 2020, PMC7067213）：
  英格兰 mcr-1 Typhimurium 含 ST34×12 + **ST19×1** + ST36×6，且该株为双相血清型——证据链倾向管线判定正确、
  gold 值属未验证推断；终局确认待论文 Table S1 / EnteroBase 注册访问
- 测试 1373 → **1376**（+3：N/A ST 跳过 / mcr 归一 / 行长预算）

### Fixed — V0.7 基准轮发现的管线存量 bug（2026-09-07）

- **.smk f-string params 路径空格 bug（严重）**：`species.smk` / `vpara.smk` / `dec_shigella.smk` / `annotation.smk`
  共 10 处 `lambda wc: str(WORKDIR) + f"/{wc.sample}/..."` 在 snakemake 7.32 shell format 中展开为带空格路径，
  python 调用与 fallback 重定向双双失败；该 bug 自规则重构引入后从未暴露（生产产物为旧版规则生成，时间戳未变不触发重跑）。
  修复为静态模板串 `str(WORKDIR) + "/{sample}/..."`；V0.7 基准强制全量重跑作为回归验证
  （修复前 7/68 连环失败 → 修复后 4/4 全链路跑通）。详见 docs/known-issues.md B2
- **`verify_all` 物种判决键兼容**（见 Wave 4 条目）

### Added — V0.7 Wave 4：PDF 报告 + 96 株基准工具（project.md §2.2，2026-09-07）

- **`generate_report.py --pdf`**：HTML → PDF via headless chromium 打印
  （对 D3/phylotree.js 渲染保真，`--virtual-time-budget` 等 JS 完成），weasyprint 兜底，
  均不可用时优雅跳过；`main_args(argv)` 可测入口；实测 SAM-TYP-001 产出 3 页 PDF（chromium 1.4）
- **`scripts/benchmark_batch.py`**：三级子命令（prepare 下采样合成基准样本 / run 独立 workdir 跑批计时 /
  extrapolate 线性外推 96 株 + 渲染 `docs/benchmark-report.md`）；完全隔离
  （`samples_bench.tsv` + `results-bench/`，不触碰生产 results/）；seqkit `--two-pass` 同 seed 保配对
- **修复 Layer 2 存量缺陷**：真实 summary 的物种判决存于 `steps.species.species`（统一 species.smk 输出）
  而 `verify_all` 只读 `verdict` 键 → 全部真实样本 species 检查误报失败；现双键兼容 + 二名形归一
  （Salmonella enterica → Salmonella）。DEC/Shigella 株仍失败属 Layer 2 仅支持 Salmonella 的存量范围限制（后续版本扩展）
- 测试 1361 → **1373**（+12：PDF 转换 5 / 基准外推 5 / Layer 2 双键回归 2）

### Added — V0.7 Wave 3：分析验证 harness（project.md §12.3，2026-09-07）

- **`scripts/validate_analytical.py`**：gold_standard.jsonl 期望值 vs 管线实际输出（复用 Layer 3 的 `extract_facts`），产出 per-strain 明细 + §12.3 指标 + 目标判定，输出 `results/validation/metrics.json` 与 `validation-report.md`
- **测量学设计**：AMR `bla` 前缀归一（blaCTX-M-15 ≡ CTX-M-15）；precision 仅对 `amr.list_complete: true` 的株计算（gold 清单多为管线自产且截断至 15 基因，FP 属清单不完整而非误报，进分母会系统性低估）——当前 0 株断言完整，precision 诚实输出 no-data
- **首轮实测（7 株：6 Salmonella + CTX-008）**：物种 100%、MLST 100%、血清型 100%、AMR 灵敏度 100%（91/91）——4 项 §12.3 目标 PASS；precision 待 gold standard 扩充（Wave 3 后续）
- **`docs/validation-report.md`**：验证报告快照入库；ECO-011（阴性对照）/MCR-010 待补跑管线后纳入
- 测试 1347 → **1361**（+14：loader 2 / evaluate 7 / aggregate+render 5）

### Added — V0.7 Wave 2：三层防御 Layer 3 NLI Reflector（2026-09-07）

- **`analysis/nli_reflector.py` + `analysis/nli_types.py`**（project.md §8.2 Layer 3 补全）：
  LLM 解读文本 → atomic claims 分解（species/ST/血清型/AMR/毒力/质粒六类，确定性正则，覆盖中英文表述）
  → 与 Source of Truth 事实（summary.json）逐条比对（entailed/contradicted/unverifiable）
  → contradiction rate 超阈值（默认 0.1）触发 `NEEDS_HUMAN_REVIEW`
- **`bio_verify_result` 挂接 Layer 3**：新增可选 `interpretation_text` 参数（schema 同步），响应新增 `layer3` 段（verifiable/contradicted 计数、rate、逐 claim 判定）；`needs_human_review` 时自动落 GOM 审计事件
- **GOM 新事件类型 `nli_reflected`**：记录 sample_id、contradiction_rate、review 标记，供人审回溯 AI 解读
- **interpret-results SKILL.md 新增「Interpretation Self-Verification」章节**：要求 Agent 在向用户呈现解读前先经 Layer 3 反射，contradicted 即修正重验
- **真实数据冒烟验证**：SAM-TYP-001（Salmonella ST19 Typhimurium）——正确解读 5/5 entailed；含虚假基因/错误 ST/错误血清型的"幻觉"文本 5/5 contradicted → review 正确触发
- 测试 1316 → **1347**（+31：extract_facts 6 / decompose_claims 9 / reflect 9 / GOM 事件 3 / 工具集成 3 / 冻结性 1）

### Changed — V0.7 立项「验证与防御闭环」+ Wave 1 文档对账（2026-09-07）

- **project.md V0.5 → V0.7**：路线图框与实际交付对齐（V0.3 形态调整说明、V0.4/V0.5 实际交付内容、
  新增 V0.6 cgMLST 溯源条目、V0.7 立项 Layer 3 NLI Reflector + 分析验证 harness + 96 株基准 + PDF 报告；
  V1.0 项维持触发条件推迟）；文档头部新增 V0.5→V0.6 / V0.6→V0.7 变更记录；页脚版本同步
- **计数统一（实测）**：tools 24 → **25**（bio_cgmlst）；Snakemake rules 24 → **30**（11 个 rule 文件：25 常规 + 4 cgMLST cohort 门控 + `rule all`）；tests 1051 → **1316**（README / docs/index.md / docs/features.md 头部）
- **features.md V0.6 → V0.7**：§3.2 高层工具表补 `bio_cgmlst`（16 → 17）；§4 规则清单补 `amr_amrfinderplus`、`vpara_serotype`、`genome_annotation`、`taxonomy_validation`、cgmlst 5 条规则（含 cohort 门控标注）
- **README species_identifier 表述修正**：「双模式：marker genes / GTDB-Tk」→ marker 五基因模式；GTDB-Tk 标准模式实际位于 `analysis/taxonomic_validator.py`（经 `taxonomy_validation` rule 接入）
- **known-issues A5 关闭**：代码库无 `bio_analyze_salmonella` 残留（仅 CHANGELOG 历史条目），无需改名
- **known-issues 测试状态刷新**：1316 passed, 0 failed

### Changed — 阶段 3 结构重构 + 质量改进（2026-07-18）

- **ReadMapper 长读段路由（M2）**：新增 `read_type` 参数（short/long）+ FASTQ 内容嗅探（前 ~100 条记录 ≥1000bp 判长读段，支持 .gz）;`bio_align` schema 同步暴露
- **SAM 流式管道（M3）**：aligner stdout 经 Popen 管道直连 `samtools sort`，消除全量 SAM 内存缓冲（大样本 OOM 风险）;stderr 落临时文件避免死锁
- **AMRFinderPlus 集成**：pixi 新增 `ncbi-amrfinderplus 3.12`（4.x libcurl/libzlib 与环境冲突）;`amr_amrfinderplus` rule（按物种映射 --organism）+ `collect_summary.py` 接入 `steps.amr.amrfinderplus`;rules 24 → 25
- **tools.py 拆包**：1887 行上帝模块 → `tools/` 包（seq / cli / pipeline / services + `_common` 共享基座），`registry.py` 表驱动注册；新增 `@tool_handler` 装饰器统一错误兜底，补齐 5 个无保护 handler
- **vpa_serotyper_engine 拆分**：1027 行 → `_vpa_kmer` / `_vpa_genes` / `_vpa_report` + 430 行编排 facade；6 个嵌套闭包收敛为纯函数，6 处全库扫描收敛为 `_RefFasta` 缓存
- **样本状态逻辑收敛**：新增 `services/sample_summary.py`，`run_analysis.py` 与 `web/app.py` 共用
- **循环依赖破环**：`species_identifier` 删除 `mode="standard"` 透传分支，依赖单向化
- **子包导出**：`analysis/` `services/` `typing/` 补 `__init__.py` 导出 + `__all__`
- **sourmash API 迁移**：`load_signatures` → `load_file_as_signatures`，`save_signatures` → `SaveSignaturesToLocation`，45 条 deprecation warning 清零
- **`~~~` header 解析收敛**：`kma._parse_template` 与 `gene_scanner._parse_db_header` 合并为 `utils.parse_db_header`
- **MinimapBackend kwargs 修复**：加 `_PARAM_MAP` + bool 裸 flag + None 跳过 + threads 替换（原会生成 `-c True` 这类错误命令行）
- **CI**：新增 `snakemake-dag` job（179-job DAG dry-run 验证）；unit-tests job 安装 web extra 运行 FastAPI 冒烟测试

### Added — 测试扩充（994 → 1042）

- `test_web_app.py`：13 个 FastAPI TestClient 冒烟测试（samples/status/snp/search/metadata/lab-results 路由）
- `test_vpa_e2e.py`：5 个端到端测试（RIMD 2210633 真实基因组 → O3:K6 Perfect；Salmonella/E. coli 阴性对照）
- `test_sample_summary.py`：20 个样本状态共用层测试
- MinimapBackend kwargs（4）+ `parse_db_header`（6）测试

### Changed — V0.4 架构精简

- **物种鉴定统一**：species_identifier.py 合并 4 个独立 rule（invA/ipaH/vpara/uidA）→ 1 个 BLAST 调用（species_markers.fasta，5 条序列）
- **ecoh_serotyper 瘦身**：330→121 行，BLAST 逻辑委托给 gene_scanner（零代码重复）
- **shigella_serotyper 新增**：移植 ShigATyper（CFSAN），支持 58 种 Shigella 血清型（S. flexneri 1a-7b/Y/Yv, S. sonnei, S. dysenteriae 1-15, S. boydii 1-20）
- **gene_scanner 框架**：通用 BLAST 引擎（替代 abricate 概念），支持任意 abricate 格式数据库
- **血清型分流**：Shigella→shigella_serotyper，DEC/EIEC→ecoh_serotyper，Salmonella→SISTR（collect_summary.py 中 primary_serotype 字段）
- **bio_gene_scan Hermes tool**：LLM 可直接扫描任意数据库
- **代码审计**：9 个 subprocess.run 加 timeout，SHA256 改分块读取，scripts/_common.py 提取共享路径
- **10/10 株全量数据刷新**：所有 summary.json 统一为最新格式（species_id + ecoh_serotype + shigella_serotype + pathotype）

### Changed — V0.2 完成标记

- **V0.2 DEC + Shigella 扩展全部完成**：
  - 10 株端到端验证通过（6 Salmonella + 1 S. Typhi + 1 E. coli + 1 Shigella + 1 EIEC）
  - 三基因物种鉴定矩阵 100% 准确（invA/uidA/ipaH 零交叉反应）
  - ECTyper + pathotype + ipaH BLAST 全部集成到 Snakemake DAG（84 jobs）
  - Snakemake workflow 扩展：dec_shigella.smk（3 新 rule + call_pathotype.py）
  - ipaH BLAST DB 路径修复（ecoli_ipaH_blastdb → ipaH_blastdb）
  - report.smk + collect_summary.py 新增 DEC 字段

### Added — V0.2 DEC + Shigella 扩展 + Gold standard 补充

- **靶基因三物种鉴定体系**：
  - invA (Salmonella, M90846.1, 2176 bp) — V0.1 已验证
  - **uidA** (E. coli/DEC, NC_000913.3, 1190 bp) — V0.2 新增
  - **ipaH** (Shigella/EIEC, NC_004337.2, 1827 bp) — V0.2 新增
  - 三基因交叉验证矩阵全部通过（invA/uidA/ipaH 无交叉反应）

- **DEC 分析模块** (`workflows/salmonella/rules/dec_shigella.smk`)：
  - ECTyper 血清型 rule（dec_ectyper）
  - pathotype 判断脚本（call_pathotype.py: STEC/EPEC/EIEC/ETEC/EAEC）
  - ipaH BLAST rule（dec_ipaH_blast，替代 ShigEiFinder）
  - report.smk + collect_summary.py 新增 DEC 字段

- **Gold standard 补充**：
  - SAM-CTX-008: S. Typhi CTX-M-15 (ERR2059823, ENA MD5 ✅, invA 1737 reads ✅)
  - SAM-MCR-010: S. Typhimurium mcr-1 (ERR2594882, R1 MD5 ✅, R2 下载损坏待修复)
  - SAM-CTX-009 (CTX-M-14): 跳过（无公开 FASTQ 的菌株）
  - SAM-PAN-007 (pansusceptible): 用 SAM-NEW-006 替代

- **代码清理**：
  - tools.py `_PROJECT_ROOT` 去重（统一到文件头）
  - `_PIXI_ENV` 全局 PATH 注入（底层 tool handler 自动找到 pixi 工具链）

### Added — Sprint 2-3: Snakemake 集成 + AI 解读 + 报告 + Hermes 部署

- **6 株端到端批量分析完成**：
  - Snakemake DAG 一次命令自动编排 62 个 job（6 株 × 10 步）
  - 全部通过：fastp → Shovill → blastn(invA) → gmlst → SISTR → abricate(CARD/VFDB/PlasmidFinder) → report
  - 物种验证 6/6 ✅，MLST/血清型/AMR 全部产出

- **GOM 入库** (`scripts/ingest_results.py`)：
  - 智能去重（相同 pipeline 跳过，不同 pipeline 创建新版本）
  - 文件产物注册（SHA256 + size）+ 事件流（uploaded → qc → assembly → amr → report）
  - 三元证据链（strain_id + pipeline_version + database_versions + tool_versions）
  - 7 ANALYSIS objects, 63 file artifacts, 35 events in SQLite

- **Deterministic Verifier** (`src/hermes_bacmap/deterministic_verifier.py`)：
  - 21 TDD tests，6 株真实数据验证全通过
  - 检查：species 确认 / MLST 完整性 / 血清型有效性 / AMR 基因合理性
  - 关键耐药标记（CTX-M/NDM/KPC/mcr-1）自动触发人工审核

- **HTML 报告生成** (`scripts/generate_report.py`)：
  - 6 株报告已生成（含 Verifier 结果 + 三元证据链 + AMR/毒力/质粒基因表）

- **Hermes 插件 13 tools**（8 底层 + 5 高层）：
  - 高层：bio_analyze_salmonella / bio_get_result / bio_verify_result / bio_generate_report / bio_list_samples
  - 底层 tool handler 自动注入 pixi PATH（`_PIXI_ENV`），不依赖 Hermes 全局 PATH
  - 端到端自然语言交互验证通过（GLM-5.2 via Z.AI）

- **Gold standard 数据修正**：
  - MLST 字段用 gmlst 真实输出替换（之前 CSV 中为幻觉数据）
  - 血清型用 SISTR 真实输出更新
  - AMR/毒力/质粒用 abricate 真实输出更新
  - E. coli 阴性对照改用 K-12 MG1655 DRR198806（benchmark reference strain）

- **交互式使用指南** (`docs/hermes-chat-guide.md`)：
  - 7 个日常工作流场景 + 完整对话示例 + 故障排查

- **invA 物种验证完整矩阵通过** (灵敏度 100% + 特异性 100%):
  - 6 株 Salmonella Gold standard: invA mapped reads 616-1221 → 全部 ✅ 阳性
  - 1 株 E. coli MG1655 (DRR198806, 8M reads PE300): invA mapped reads = **0** → ✅ 阴性
  - 灵敏度 6/6 = 100%；特异性 1/1 = 100%
  - invA (M90846.1, FDA BAM Chapter 5) 作为 Salmonella 属特异性靶基因的有效性确认

- **E. coli MG1655 阴性对照** (SAM-ECO-011 / DRR198806):
  - 最干净的 WT K-12 MG1655（"Benchmarks of de novo assemblers" 参考标准）
  - MiSeq PE300, 4.05M reads, 1.9 GB
  - MD5 校验通过（ENA 双源验证）
  - 替代了数据质量差的 ATCC 25922 SRR2889879（实际是 454 数据）

- **组装子 blastn 物种验证方法** (`scripts/assembly_validation_blastn.sh`):
  - blastn contigs → invA BLAST 数据库（identity > 90%, coverage > 80%）
  - 补充 reads-based bwa 方法（两层验证：快速筛查 + 组装确认）
  - minimap2 替代版本也已就位（`scripts/assembly_validation_minimap2.sh`）

- **pixi 全量工具安装完成** (bioconda 清华镜像配置):
  - blastn/makeblastdb 2.17.0+, spades.py 3.15+, seqkit, bedtools 全部安装
  - 关键修复：配置 `~/.config/pixi/config.toml` bioconda 清华镜像（31.7 MB/s vs 之前超时）

- **Salmonella invA 物种验证** (`scripts/species_validation_invA.sh`):
  - bwa mem + samtools flagstat 把 reads 比对到 invA 靶基因（M90846.1）
  - 6/6 株 Salmonella Gold standard 全部通过验证（mapped reads 616-1221，远超 100 阈值）
  - mapping rate 0.04-0.07% 符合理论预期（invA 2.2kb / 基因组 4.8Mb ≈ 0.046%）
  - 替代 Kraken2 通用分类器，符合"针对性 4 病原检测"设计

- **invA 靶基因参考数据库** (`data/reference/salmonella_invA.fasta`):
  - M90846.1 (S. Typhimurium invA complete cds, 2176 bp) — FDA BAM Chapter 5 标准参考
  - bwa index 索引已生成

- **Gold standard FASTQ 下载** (`scripts/download_gold_standard.py`):
  - ENA HTTPS + aria2c 多线程下载（含 MD5 自动校验）
  - 6 株 Salmonella × 2 files = 12 个 FASTQ，总 1.5 GB，全部 MD5 通过
  - CSV fastq_r1_path / fastq_r2_path 已更新

- **GenomeObjectService 完整实现** (`src/hermes_bacmap/genome_object_service.py`):
  - SQLite + WAL + JSON 列 + FTS5 后端，4 张表（genome_objects / genome_objects_fts / events / file_artifacts）+ 5 个索引
  - `__post_init__` 校验：object_type 枚举、version 正整数、schema_version semver、ANALYSIS 证据链（pipeline_version + database_versions 强制）
  - CRUD：create / read / list_by_type / list_by_organism（含分页，默认返回最新版本）
  - 版本管理：create_new_version / get_latest_version / list_versions / delete（Immutable 永远拒绝）
  - 文件产物：register_file_artifact / list_file_artifacts（含 SHA256 + size 实时校验）
  - 事件流：log_event / list_events（含 timezone-aware UTC、since 时间过滤）
  - Context manager：`__enter__` / `__exit__` / close
  - **61 个 TDD 测试全部通过**（Sprint 0 的 43 红 + 18 绿 → 61 全绿）

### Changed — Sprint 1

- `tests/conftest.py`: `sample_genome_object` fixture 使用独立 object_id（与 `sample_sample_object` 区分），避免多对象场景冲突
- `tests/fixtures/gold_standard/salmonella/gold_standard.csv`: 移除 "truncate PE250 to PE150" 建议（组装工具自动适配读长）

### Added — Sprint 0: Quality infrastructure + Gold standard preparation

- **Salmonella Gold standard sample set** (`tests/fixtures/gold_standard/salmonella/`):
  - `gold_standard.csv` + `gold_standard.jsonl`: 11 strains (10 Salmonella + 1 E. coli negative control)
  - 6 strains VERIFIED via NCBI webfetch (BioSample + SRA both confirmed)
  - 1 strain PARTIALLY VERIFIED (BioSample confirmed, SRA needs lookup)
  - 4 strains GAP placeholders with explicit NCBI Pathogen Detection queries
    for pansusceptible / blaCTX-M-15 / blaCTX-M-14 / mcr-1 Salmonella
  - `data_dictionary.md`: 31-field schema with data sources and dual-source verification rules
  - `README.md`: sample distribution targets and acceptance criteria
  - Coverage: 2 S. Typhimurium (ST19/34), 2 S. Enteritidis (ST11),
    1 S. Infantis (ST32 with pESI), 1 S. Newport (ST45), 1 E. coli ATCC 25922
    (CLSI QC reference — critical species-specificity negative control)
  - Implements `project.md` §12.3 analytical validation

- **pytest fixtures** (`tests/conftest.py`): `gold_standard_set`,
  `salmonella_gold_standard`, `negative_control` (session-scoped, ready for
  Sprint 4 analytical validation tests)

- **Genome Object Model (GOM) service skeleton** (`src/hermes_bacmap/genome_object_service.py`):
  - `GenomeObject`, `FileArtifact`, `Event`, `CompositeTriplet` dataclasses
  - `ObjectType` enum (7 types: sample/analysis/report/workflow/plugin/knowledge/task)
  - `EventType` literal (11 standard events: uploaded → qc_finished → ... → report_generated)
  - `GenomeObjectService` API surface (CRUD + versioning + file artifacts + events)
  - All methods raise `NotImplementedError` as TDD red starting point
  - Implements `project.md` §5.1 (standard schema), §5.2 (Composite Triplet), §5.4 (SQLite schema)

- **TDD unit test suite** (`tests/unit/test_genome_object_service.py`):
  - 7 test classes, ~60 test cases covering: schema validation, Composite Triplet,
    evidence chain (§4.5), CRUD, Immutable versioning (§4.6), file artifacts, events
  - All tests expected to fail (NotImplementedError) until Sprint 1 implements GOS
  - Shared fixtures in `tests/conftest.py` (sample AMR payload, Salmonella analysis object)

- **GitHub Actions CI pipeline** (`.github/workflows/ci.yml`):
  - lint (ruff check + format), typecheck (mypy --strict), unit-tests (pytest + coverage),
    pre-commit hooks, security-scan (pip-audit), changelog-check
  - Coverage uploaded to Codecov; PR cannot merge without CHANGELOG.md update
  - Implements `project.md` §12.7

- **Pre-commit hooks** (`.pre-commit-config.yaml`):
  - ruff, mypy --strict, markdownlint, trailing-whitespace, detect-secrets
  - Implements `project.md` §12.6

- **Salmonella Gold standard sample set (11 strains)** (`tests/fixtures/gold_standard/salmonella/gold_standard.csv`):
  - Implements `project.md` §12.3 analytical validation spec
  - 7 verified strains (BioSample + SRA both confirmed via webfetch): 2 S. Typhimurium (ST19/ST34), 2 S. Enteritidis ST11,
    1 S. Infantis ST32 with pESI megaplasmid (blaCTX-M-65 ESBL), 1 S. Newport ST45, 1 E. coli ATCC 25922 (CLSI AST QC reference)
  - 3 partial-verified strains (BioSample confirmed, SRA pending Run Selector): GenomeTrakr 2017 PT Typhimurium (SAMN11787766), PulseNet Enteritidis (SAMN07568553)
  - 4 pending strains with explicit NCBI Pathogen Detection queries for completion: pansusceptible, ESBL blaCTX-M-15, ESBL blaCTX-M-14, mcr-1
  - JSONL mirror synced with CSV (schema-validated, conftest.py fixtures load correctly)
  - V0.2 expansion pool: 1 verified S. Heidelberg (SAMN01832089, CFSAN002069) documented in README

- **Project plan V0.2** (`project.md`, 1200 lines):
  - Replaced V0.1 architecture (HPC/Nextflow/MongoDB/MinIO) with personal Linux workstation +
    Snakemake + SQLite + local filesystem stack
  - Added §12 Development Quality Assurance (12 subsections: test pyramid, TDD strategy,
    analytical validation, regression testing, AI output validation, engineering practices,
    CI/CD, data integrity, performance benchmarks, security testing, accessibility, traceability)
  - Added Sprint 0 (week 0) to V0.1 development roadmap
  - Defined 4 target foodborne pathogens (Salmonella MVP, DEC, Shigella, V. parahaemolyticus)

### Changed

- `pyproject.toml`: added mypy and pydantic to dev/runtime dependencies for GOM schema validation

[Unreleased]: https://github.com/indexofire/hermes-bacmap/releases
