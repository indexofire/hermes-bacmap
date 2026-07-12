# 尚存问题清单

> **最后更新**: 2026-07-04
> **测试状态**: 96 passed, 0 failed
> **来源**: 代码审计（engine 层 + pipeline 脚本）

---

## 🟠 Medium — 防御性改进

### M1. MinimapBackend kwargs 盲传

- **位置**: `src/hermes_bacmap/engine/backends/blast.py:158-160`
- **问题**: `MinimapBackend.find()` 的 kwargs 循环直接将每个 key-value 拼成 `-key value`，无参数映射表（`_PARAM_MAP`）、无 bool 处理、无 skip None。如果调用方传 `c=True`，会生成 `-c True`（错误——应为 `-c`）。
- **当前影响**: 无。当前无调用方向 MinimapBackend 传 bool kwargs。
- **修复方案**: 参考 `BlastBackend.find()` 的 kwargs 处理逻辑，加 `_PARAM_MAP` + bool 分支 + skip 已在 cmd 中的参数。
- **优先级**: 等需要扩展 minimap2 参数时再修。

### M2. ReadMapper 长读段路由错误

- **位置**: `src/hermes_bacmap/engine/read_mapper.py:145-150`
- **问题**: `_select()` 只检查 FASTA 扩展名来决定是否用 minimap2。所有 FASTQ（含 ONT/PacBio 长读段）默认走 BWA-MEM，性能差。
- **当前影响**: 无。当前管线只有 Illumina 短读段数据。
- **修复方案**: 增加 `read_type` 参数（"short"/"long"），或从文件名/内容嗅探读段长度。
- **优先级**: 等接入长读段数据时再修。

### M3. SAM 全量内存缓冲

- **位置**: `src/hermes_bacmap/engine/read_mapper.py:67,98`
- **问题**: `bwa mem` / `minimap2` 的完整 SAM 输出读入 `proc.stdout`（Python str），再传给 `samtools sort`。50× WGS 样本的 SAM 可达 5-10GB，有 OOM 风险。
- **当前影响**: 低。当前样本（~4.9Mb 基因组，~100× 覆盖度）SAM 约 2-3GB，在 62GB RAM 上可运行。
- **修复方案**: 改用 `subprocess.Popen` 管道直连 aligner stdout → samtools sort stdin，避免全量缓冲。
- **优先级**: 等处理大基因组（>10Mb）或高覆盖度（>200×）时再修。

---

## 🟡 Low — 装饰性 / 边缘情况

### L1. ensure_index FASTA 候选列表不完整

- **位置**: `src/hermes_bacmap/engine/backends/blast.py:59-63`
- **问题**: `ensure_index()` 在 BLAST 索引不存在时尝试从 FASTA 重建，候选扩展名为 `.fasta`、`_sequences.fasta`、`_abricate.fasta`，缺少 `.fna`、`.fa`。
- **当前影响**: 无。现有数据库都使用 `_sequences.fasta` 或 `_abricate.fasta` 后缀。
- **修复方案**: 在候选列表中添加 `.fna`、`.fa`、`.fna.gz` 等。

### L2. available() 返回静态列表

- **位置**: `src/hermes_bacmap/engine/backends/__init__.py:42-43`
- **问题**: `available()` 返回 `_BUILTINS.keys()`（硬编码内置后端名），不反映通过 `register()` 动态注册的自定义后端。
- **当前影响**: 无。当前无自定义后端注册。
- **修复方案**: 合并 `_BUILTINS.keys()` 和 `_REG.available().keys()`。

### L3. (已完成 — 2>/dev/null 已清理)

- **位置**: `workflows/salmonella/rules/snp.smk`（多个 shell 块）
- **问题**: `bwa mem`、`bcftools mpileup/call`、`bcftools reheader/view/index` 的 stderr 都被 `2>/dev/null` 丢弃。工具失败时无诊断信息。
- **当前影响**: 当 SNP 管线失败时，Snakemake 只显示 "Error code 1"，无 stderr 输出。
- **修复方案**: 将 `2>/dev/null` 改为 `2>{log}` 写入日志文件，或完全移除让 Snakemake 捕获。
- **优先级**: 中。下次修改 snp.smk 时一并处理。

### L4. 19 个 E501 行过长 + 12 个文件格式不规范

- **位置**: `deterministic_verifier.py`、`ecoh_serotyper.py`、`gene_scanner.py`、`genome_annotator.py`、`genome_object_service.py`、`schemas.py`、`shigella_serotyper.py`、`tools.py`
- **问题**: 19 处行宽超过 100 字符（ruff E501），12 个文件不符合 ruff format 规范。
- **当前影响**: 纯装饰性，不影响运行。
- **修复方案**: `ruff format src/hermes_bacmap/ && ruff check --fix src/hermes_bacmap/`

### L5. (已完成 — annotation 已加入 rule all)

- **位置**: `workflows/salmonella/Snakefile:rule all`
- **问题**: `rule all` 包含 per-sample summary + SNP cohort summary，但不包含 `{sample}/annotation/annotation.json`。annotation 规则存在且可用，但需要单独触发。
- **当前影响**: `snakemake` 或 `run_analysis.py --all` 不会自动运行注释。
- **修复方案**: 在 `rule all` 的 input 中添加 `expand(str(WORKDIR) + "/{sample}/annotation/annotation.json", sample=SAMPLES)`。
- **优先级**: 等确定注释是否为所有样本的必选步骤后再决定。

### L6. tools.py 中 sys.path.insert 运行时路径修改

- **位置**: `src/hermes_bacmap/tools.py`（5 处：lines 798, 1203, 1272, 1300, 1358）
- **问题**: 多个 tool handler 内部使用 `sys.path.insert(0, str(_PROJECT_ROOT / "src"))` 来导入 hermes_bacmap 模块。这是运行时路径修改，不够干净。
- **当前影响**: 无功能问题。但如果 Hermes 环境已有 hermes_bacmap 在 path 中，insert 是冗余的。
- **修复方案**: 在 `tools.py` 文件头统一做一次 `sys.path.insert`，或通过 plugin 机制确保模块已在 path 中。

---

## 架构决策待定

### A1. (已完成 — V.para 血清型已实现)

- **状态**: ✅ 已完成 (VpaSerotyper, 移植自 vpautils)
- **参考**: docs/architecture/engine.md (engine 层 MashBackend/SourmashBackend)

### A2. GBrain embedding 待配置

- **状态**: GBrain v0.42.57.0 已安装，PGLite 已初始化，10 页面已导入
- **待办**: 配置 embedding（推荐 `ollama:nomic-embed-text`），启用向量搜索和 `gbrain think` 综合回答
- **文档**: `docs/architecture/gbrain.md`

### A3. AMRFinderPlus 集成

- **状态**: config.yaml 有配置但无 .smk 规则。实际只用 abricate (CARD/VFDB/PlasmidFinder)
- **优先级**: 低

### A3. R ggtree 可视化环境

- **状态**: pixi solver 与现有依赖冲突；系统 R 4.6 cpp11 不兼容
- **替代方案**: conda create -n r-viz -c bioconda -c conda-forge r-base=4.4 r-ggplot2 bioconductor-ggtree

### A4. 端到端集成测试（CI）

- **状态**: CI 只跑 96 个 unit tests，无 Snakemake DAG 端到端测试
- **优先级**: 中

### A5. Tool 重命名（可选）

- **状态**: `bio_analyze_salmonella` → `bio_analyze_pathogen`？名称暗示只支持 Salmonella，但实际支持 4 种病原
- **风险**: 低（LLM 每次会话重新读 schema）
- **优先级**: 低
