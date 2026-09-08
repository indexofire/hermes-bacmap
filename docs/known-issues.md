# 尚存问题清单

> **最后更新**: 2026-09-07
> **测试状态**: 1415 passed, 0 failed
> **来源**: 代码审计 Round 1-9（58 bugs 已修复）

---

## 🟠 Medium — 防御性改进

### M1. (已完成 — MinimapBackend kwargs 参数映射 + bool 处理)

- **位置**: `src/hermes_bacmap/engine/backends/minimap2.py`
- **问题**: `MinimapBackend.find()` 的 kwargs 循环直接将每个 key-value 拼成 `-key value`，无参数映射表（`_PARAM_MAP`）、无 bool 处理、无 skip None。如果调用方传 `c=True`，会生成 `-c True`（错误——应为 `-c`）。
- **修复**(2026-07-18): 参照 `BlastBackend.find()` 的模式——加 `_PARAM_MAP`(pythonic 名 → minimap2 短选项)、bool True 生成裸 flag、bool False/None 跳过、`threads` kwarg 替换已有 `-t` 值而非追加。新增 4 个单测覆盖。

### M2. (已完成 — ReadMapper 长读段路由)

- **位置**: `src/hermes_bacmap/engine/read_mapper.py`
- **问题**: `_select()` 只检查 FASTA 扩展名来决定是否用 minimap2。所有 FASTQ（含 ONT/PacBio 长读段）默认走 BWA-MEM，性能差。
- **修复**(2026-07-18): `ReadMapper.map()` 新增 `read_type` 参数（"short"/"long");`read_type` 缺省时自动嗅探 FASTQ 前 ~100 条记录（≥1000bp 判长读段，支持 .gz，失败回退 short);`bio_align` tool schema 同步暴露 `read_type`。

### M3. (已完成 — SAM 管道流式传输)

- **位置**: `src/hermes_bacmap/engine/read_mapper.py`
- **问题**: `bwa mem` / `minimap2` 的完整 SAM 输出读入 `proc.stdout`（Python str），再传给 `samtools sort`。50× WGS 样本的 SAM 可达 5-10GB，有 OOM 风险。
- **修复**(2026-07-18): 新增 `_run_align_and_sort()`,aligner stdout 经 `Popen` 管道直连 `samtools sort` stdin，零全量缓冲;aligner stderr 写临时文件避免管道死锁，失败时随异常抛出。已用真实 bwa/minimap2 冒烟验证。

---

## 🟡 Low — 装饰性 / 边缘情况

### L1. (已完成 — 添加 .fna/.fa 候选扩展名)

- **位置**: `src/hermes_bacmap/engine/backends/blast.py:50-56`
- **问题**: `ensure_index()` 在 BLAST 索引不存在时尝试从 FASTA 重建，候选扩展名为 `.fasta`、`_sequences.fasta`、`_abricate.fasta`，缺少 `.fna`、`.fa`。
- **当前影响**: 无。现有数据库都使用 `_sequences.fasta` 或 `_abricate.fasta` 后缀。
- **修复方案**: 在候选列表中添加 `.fna`、`.fa`、`.fna.gz` 等。

### L2. (已完成 — available() 合并动态注册后端)

- **位置**: `src/hermes_bacmap/engine/backends/__init__.py:42-43`
- **问题**: `available()` 返回 `_BUILTINS.keys()`（硬编码内置后端名），不反映通过 `register()` 动态注册的自定义后端。
- **当前影响**: 无。当前无自定义后端注册。
- **修复方案**: 合并 `_BUILTINS.keys()` 和 `_REG.available().keys()`。

### L3. (已完成 — 2>/dev/null 已清理)

- **位置**: `workflows/bacmap/rules/snp.smk`（多个 shell 块）
- **问题**: `bwa mem`、`bcftools mpileup/call`、`bcftools reheader/view/index` 的 stderr 都被 `2>/dev/null` 丢弃。工具失败时无诊断信息。
- **当前影响**: 当 SNP 管线失败时，Snakemake 只显示 "Error code 1"，无 stderr 输出。
- **修复方案**: 将 `2>/dev/null` 改为 `2>{log}` 写入日志文件，或完全移除让 Snakemake 捕获。
- **优先级**: 中。下次修改 snp.smk 时一并处理。

### L4. (已完成 — 所有 E501 长行已修复)

- **位置**: `deterministic_verifier.py`、`ecoh_serotyper.py`、`gene_scanner.py`、`genome_annotator.py`、`genome_object_service.py`、`schemas.py`、`shigella_serotyper.py`、`tools.py`
- **问题**: 19 处行宽超过 100 字符（ruff E501），12 个文件不符合 ruff format 规范。
- **当前影响**: 纯装饰性，不影响运行。
- **修复方案**: `ruff format src/hermes_bacmap/ && ruff check --fix src/hermes_bacmap/`

### L5. (已完成 — annotation 已加入 rule all)

- **位置**: `workflows/bacmap/Snakefile:rule all`
- **问题**: `rule all` 包含 per-sample summary + SNP cohort summary，但不包含 `{sample}/annotation/annotation.json`。annotation 规则存在且可用，但需要单独触发。
- **当前影响**: `snakemake` 或 `run_analysis.py --all` 不会自动运行注释。
- **修复方案**: 在 `rule all` 的 input 中添加 `expand(str(WORKDIR) + "/{sample}/annotation/annotation.json", sample=SAMPLES)`。
- **优先级**: 等确定注释是否为所有样本的必选步骤后再决定。

### L6. (已完成 — sys.path.insert 已全部移除)

- **位置**: `src/hermes_bacmap/tools.py`（5 处：lines 798, 1203, 1272, 1300, 1358）
- **问题**: 多个 tool handler 内部使用 `sys.path.insert(0, str(_PROJECT_ROOT / "src"))` 来导入 hermes_bacmap 模块。这是运行时路径修改，不够干净。
- **当前影响**: 无功能问题。但如果 Hermes 环境已有 hermes_bacmap 在 path 中，insert 是冗余的。
- **修复方案**: 在 `tools.py` 文件头统一做一次 `sys.path.insert`，或通过 plugin 机制确保模块已在 path 中。

---

## 架构决策待定

### A1. (已完成 — V.para 血清型已实现)

- **状态**: ✅ 已完成 (VpaSerotyper, 移植自 vpautils)
- **参考**: docs/architecture/engine.md (engine 层 MashBackend/SourmashBackend)

### A2. GBrain embedding 待配置（受阻 — ollama 未安装）

- **状态**: GBrain v0.42.57.0 已安装，PGLite 已初始化，10 页面已导入
- **受阻**(2026-07-18 评估): `~/.local/bin/ollama` 是内容为 "Not Found" 的失效文件（下载失败的占位）,ollama 实际未安装;embedding 需要可用的 ollama 服务（`nomic-embed-text`)。安装 ollama 属系统级变更，待用户决定
- **文档**: `docs/architecture/gbrain.md`

### A3. (已完成 — AMRFinderPlus 集成)

- **状态**: ✅ 2026-07-18 完成。pixi 装 `ncbi-amrfinderplus 3.12`(4.x 的 libcurl/libzlib 与现有环境冲突);
  `typing_amr.smk` 新增 `amr_amrfinderplus` rule（按样本物种映射 --organism,V.para 无对应 organism 则省略）;
  `report.smk` + `collect_summary.py` 接入 `steps.amr.amrfinderplus`;`run_analysis.py --status` 解读本已消费该字段

### A3. R ggtree 可视化环境（不处理 — 维持文档替代方案）

- **状态**: pixi solver 与现有依赖冲突；系统 R 4.6 cpp11 不兼容；本机无 conda/mamba
- **评估**(2026-07-18): 纯可视化用途且 `generate_report.py` 已有文本 fallback tree，性价比低。维持替代方案: `conda create -n r-viz -c bioconda -c conda-forge r-base=4.4 r-ggplot2 bioconductor-ggtree`，待用户自行决定

### A4. (部分完成 — DAG dry-run + web 冒烟已入 CI)

- **状态**: ✅ 2026-07-18 已加 `snakemake-dag` CI job(pip 装 snakemake 7.32 + dummy reads,`snakemake -n` 构建 179-job DAG)与 13 个 FastAPI TestClient 冒烟测试;`_vpa_genes` 有 RIMD O3:K6 端到端测试(5 个)
- **剩余**: 无真实数据的全流程 Snakemake 执行测试(需 gold_standard FASTQ,体量大,暂不入 CI)

### A5. Tool 重命名（已关闭 — 无残留）

- **状态**: ✅ 2026-09-07 核查关闭。代码库中已无 `bio_analyze_salmonella` 残留（唯一命中为 CHANGELOG.md 历史条目，属正常历史记录）；现行名称 `bio_analyze_pathogen` 已在 `tools/registry.py` 注册，schema 同步。无需进一步改名。

---

## 🟠 B 系列 — V0.7 基准轮发现（2026-09-07）

### B1. 基准全量计时在本机不稳定（低深度组装 × 并发超卖）

- **位置**: `scripts/benchmark_batch.py run`（AMD Ryzen 7 5700G，8c/16t）
- **问题**: 150k 读段下采样样本在 cores=15（4×fastp --thread 8 超卖）或低覆盖
  pilon 纠错（coverage 7 < minDepth 5 边缘）下偶发 assembly/qc 失败，无法完成
  单次干净全量计时；cores=8 增量重跑稳定。
- **当前影响**: 基准外推基于分段保守合成计时（`bench_timing.json.timing_source`
  有标注）；生产全读深数据不受影响（覆盖度远高于下采样）。
- **修复方案**: 推荐档硬件复测；或 bench 样本提高至 ≥300k 读段 + rule 级
  threads/资源声明（snakemake resources mem_mb 约束，project.md §11.3）。
- **优先级**: 中（V0.8 候选）。

### B2. .smk f-string params 路径空格 bug（✅ 已修复 2026-09-07）

- **位置**: `species.smk` / `vpara.smk` / `dec_shigella.smk` / `annotation.smk`
- **问题**: `params: out = lambda wc: str(WORKDIR) + f"/{wc.sample}/..."` 形式的
  f-string lambda 在 snakemake 7.32 shell format 中展开为带空格路径
  （`out / SAMPLE /x.json`），python -c 与 fallback 重定向双双失败——
  该 bug 自规则重构引入后从未暴露（生产产物均为旧版规则生成，时间戳未变
  不触发重跑）。
- **修复**: 10 处 f-string lambda 全部改为静态模板串
  `str(WORKDIR) + "/{sample}/..."`（format 语义已用 mini-Snakefile 验证）；
  V0.7 基准强制全量重跑作为回归验证（修复前 7/68 连环失败 → 修复后 4/4 跑通）。
- **教训**: 规则重构后应强制重跑（touch 输入或 bench 全量）做回归，仅靠
  时间戳判断会掩盖 shell 层缺陷。

### B3. species_markers BLAST 索引缺失 + fallback 写出无效 JSON（✅ 已修复 2026-09-07）

- **位置**: `data/reference/species/` 索引；`species.smk`/`dec_shigella.smk`/`vpara.smk` fallback 参数
- **问题**: (1) `species_markers` BLAST 索引不在库中（与 bench 轮发现的 shigella_ref/ecoh 同类），
  导致 f-string 修复后的 `species_identify` python 首次真实执行即 FileNotFoundError；
  (2) fallback 参数写作 `'{{...}}'`，经 snakemake 7.32 shell format 后**原样透传双花括号**，
  落盘为无效 JSON（`{{"species":...}}`）——mini-Snakefile 实验证实单花括号才是正确形态，
  原转义假设从引入之日起即错误。
- **修复**: `gene_scanner.setup_db('species_markers')` 重建索引；4 处 fallback 改单花括号
  （species ×1 / dec_shigella ×2 / vpara ×1）。ECO-011 重跑验证：uidA 100%/100% → DEC 路由正确。
- **P1 落地（2026-09-08）**: `_find_db` 已实现**缺索引懒重建**（索引缺失时自动 `setup_db`
  兜底，源 FASTA 也不存在时才抛增强错误）——fresh clone 复发路径关闭（2 个单测锁定）。
- **教训**: `|| echo fallback` 是错误兜底路径，自身也需要测试覆盖——无效 JSON 兜底比崩溃
  更危险（下游静默降级）。索引类资源已由懒重建自愈；CI 校验待 blast 二进制可用的环境再议。

### B4. SAM-MCR-010 R2 FASTQ 损坏（✅ 已修复 2026-09-07）

- **问题**: V0.2 时期下载的 R2 损坏（gzip unexpected EOF，60.8MB 截断）；CHANGELOG 曾标注
  "R2 下载损坏待修复"。
- **修复**: aria2c 8 线程断点续传重下（ENA ERR2594882_2），MD5 与 ENA 报告值一致
  （`8f4dec3005a04f556a1f3ae7b6429ce6`），gzip -t 通过，537,706 records。
- **附注**: 管线补跑完成（Salmonella/invA ✅、Typhimurium ✅、mcr-1 ✅）；MLST 判 ST19 与
  gold 期望 ST34 不一致（gold alleles 为 PENDING 未验证值）——见 docs/validation-report.md
  Strain-specific findings。2026-09-07 文献核实（Sia 2020 PMC7067213）：英格兰 mcr-1
  Typhimurium = ST34×12 + **ST19×1** + ST36×6，且该株为双相血清型（契合 ST19）——证据链
  倾向管线正确、gold 值属未验证推断；终局确认需 Table S1 / EnteroBase 注册访问。
