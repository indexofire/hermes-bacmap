# Changelog

All notable changes to hermes-bacmap are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed — 阶段 3 结构重构 + 质量改进（2026-07-18）

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
  - 7 verified strains (BioSample + SRA both confirmed via webfetch): 2 S. Typhimurium (ST19/ST34), 2 S. Enteritidis ST11, 1 S. Infantis ST32 with pESI megaplasmid (blaCTX-M-65 ESBL), 1 S. Newport ST45, 1 E. coli ATCC 25922 (CLSI AST QC reference)
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
