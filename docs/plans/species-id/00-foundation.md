# P0 · 共享地基：GOM 物种鉴定 Schema + 模式统一 + 下载框架

前置：无（本专项第一步） · 后续：A / B / C / D 全部依赖本计划 · 估算：5-6 人日

## 1. 目标

为五方法并存打地基：(1) GOM 能承载多方法鉴定结果并支持按菌株比较；(2) `species_mode` 成为统一选择面；(3) 下载脚本框架就绪，后续每库只需写"声明式"配置；(4) 现有 marker 方法回填 GOM，保证历史数据可比。

## 2. 交付物清单

| 文件 | 改动类型 | 内容 |
|---|---|---|
| `src/hermes_bacmap/services/genome_object_service.py` | 修改 | `_SPECIES_ID_REQUIRED_FIELDS` 校验 + `species_identified` EventType |
| `src/hermes_bacmap/analysis/species_identifier.py` | 修改 | `identify()` 返回值增加 method/database 元数据字段 |
| `src/hermes_bacmap/analysis/species_consensus.py` | 新增 | 多方法聚合比较 + 仲裁规则（供 verifier 与 compare 工具复用） |
| `src/hermes_bacmap/deterministic_verifier` 所在 `analysis/deterministic_verifier.py` | 修改 | 接入 species 仲裁：优先级 + 冲突 NEEDS_REVIEW |
| `src/hermes_bacmap/config.py` | 修改 | `GTDBDB` → `GTDBTK_DATA_PATH`；新增 `SPECIES_DB_DIR`（默认 `data/db/`） |
| `workflows/bacmap/config/config.yaml` | 修改 | `species_mode` 枚举扩展 + `kraken2_prefilter: false` |
| `scripts/_common.py` | 修改 | 下载公共函数（§4） |
| `scripts/setup_databases.py` | 新增 | 交互式 tier 编排器（薄壳） |
| `scripts/ingest_results.py` | 修改 | 物种鉴定结果入库函数 + marker 回填路径 |
| `scripts/run_analysis.py` | 修改 | `--species-mode` CLI 参数 |
| `src/hermes_bacmap/schemas.py` + `tools/` | 修改 | `bio_species_compare` 新 tool（第 27 个）；`bio_validate_taxonomy` 加 method 参数 |
| `tests/unit/test_species_consensus.py` 等 | 新增 | TDD，先写测试 |
| `README.md` | 修改 | 环境架构表补 mash 实况（当前 pixi.toml 无 mash） |

## 3. GOM Schema 扩展（核心）

### 3.1 校验规则（照抄 cgMLST 先例）

```python
_SPECIES_ID_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "species_identification": ("method", "database", "result"),
}
```

接入现有 `_validate_cgmlst_payload` 同一钩子位置（改名为通用 `_validate_analysis_payload`，cgMLST 与 species_identification 各自查表；其余 analysis_type 保持 opaque 直通——**additive，零迁移**）。

`result` 内部必填 `species: str` 与 `confidence: str`；`ani`/`aligned_fraction`/`top_hits` 等方法特有字段可选。method 枚举：`marker | panel | skani_gtdb | mash_refseq | sourmash | gtdbtk | kraken2`。

### 3.2 EventType 扩展

`EventType` Literal 增加 `"species_identified"`；每次入库写一条事件（payload 摘要：method + species + confidence）。

### 3.3 marker 方法回填

`species_identifier.identify()` 的 `SpeciesIdResult` 增加：

```python
method: str = "marker"
database: dict = {"name": "species_markers", "version": "<markers.fasta sha256 前 8 位>"}
```

`ingest_results.py` 新增 `_ingest_species_identification(sample, result, db_versions)`：把 `species_id.json` 转为 ANALYSIS 对象。
**存量数据回填**：`--backfill-species` 参数扫描已有 `results/*/species/species_id.json` 批量入库（幂等：已存在同 method+database_signature 的对象跳过）。

### 3.4 多方法比较（species_consensus.py）

```python
def compare(strain_id: str, service: GenomeObjectService) -> SpeciesConsensus:
    """聚合该菌株全部 species_identification 对象，输出一致性矩阵 + 仲裁结论"""
```

仲裁规则（写入 deterministic_verifier）：

1. 优先级：`gtdbtk > {skani_gtdb, panel, sourmash, mash_refseq} > marker`
2. 高层有结论 → 以高层为准，低层不一致记入 `agreement.status = "conflict"`（不否定，仅标注）
3. 同层方法之间冲突 → `NEEDS_REVIEW`（review_flags 机制已有，复用）
4. **Shigella/EIEC 豁免**：skani/gtdbtk 层判 *E. coli* 复合群 vs marker 判 Shigella 属已知同种情形，`agreement.status = "expected_divergence"`，不触发人审

## 4. 下载脚本公共框架（scripts/_common.py）

```python
def download_database(
    name: str,                    # 库名，如 "skani_gtdb"
    urls: list[str],              # 按序尝试的镜像
    dest_dir: Path,               # data/db/<name>/
    expected_md5: str | None, None,
    expected_size_gb: float,      # 预检展示 + 磁盘余量校验（要求 2 倍于压缩包）
    min_free_gb: float = 0,       # 解压后所需余量（GTDB-Tk 设 220）
    min_ram_gb: float | None = None,  # RAM 硬门禁（GTDB-Tk 设 140）
) -> Path:  # 返回解压后目录，写 manifest
```

统一行为：

- **预检**：打印体积/预计时间 → 磁盘余量不足则拒绝；`min_ram_gb` 读取 `/proc/meminfo` MemAvailable，不足则硬拒绝（GTDB-Tk 专用）
- **下载**：`wget -c --tries=5 --timeout=60`（断点续传）；支持 `--mirror` 覆盖默认 URL 顺序；支持 `HTTP(S)_PROXY` 环境变量透传
- **校验**：md5/sha256 不符 → 删除重下（最多 3 次）
- **幂等**：manifest 存在且校验通过 → 打印"已安装"直接退出 0
- **manifest**：`data/db/manifests/<name>.json`，字段：`name / version / downloaded_at / source_url / checksum / files[] / size_bytes / tool_version`——**该文件即 GOM `database.manifest` 与三元证据链的单一事实源**

`setup_databases.py`（薄编排器）：交互式列出 tier（none / mini 1-2GB / instant 159MB / full 30GB / sourmash 3.7GB / standard 101GB）→ 展示体积、RAM 需求、预计时间 → 确认后 `subprocess` 调用对应下载脚本。
结束时打印已装数据库与可用 species_mode 映射。支持非交互 `--tier mini --yes`（CI 友好）。

## 5. species_mode 统一

| 层 | 改动 |
|---|---|
| `config.yaml` | `species_mode: simple \| panel \| skani_gtdb \| mash_refseq \| sourmash \| standard`；独立键 `kraken2_prefilter: false` |
| Snakemake | `species.smk` 按 mode 分派到对应 rule（mode=standard 时仍跑 marker 作对照，GOM 双对象）；后续各方案分计划补各自 rule |
| CLI | `run_analysis.py --species-mode {simple,panel,skani_gtdb,mash_refseq,sourmash,standard}`，缺省读 config |
| Hermes tool | `bio_validate_taxonomy` schema 加 `method` 可选参数（缺省读 config）；新增 `bio_species_compare`（输入 strain_id，输出一致性矩阵 + 仲裁结论 + 各方法证据链） |
| 降级 | 目标 mode 的数据库缺失（manifest 不存在或工具不在 PATH）→ 记 warning 回退 simple，`species_id.json` 中记录降级原因——沿用现有容错哲学 |

## 6. 测试计划（TDD）

| 测试 | 内容 | 数量 |
|---|---|---|
| `test_gom_species_payload` | 必填字段缺失拒写；合法 payload 多方法并存；FTS 可检索 method | 6 |
| `test_species_consensus` | 一致 / 高低层冲突 / 同层冲突 NEEDS_REVIEW / Shigella 豁免 | 8 |
| `test_download_common` | md5 失败重试、幂等跳过、磁盘预检拒绝、RAM 门禁（monkeypatch meminfo） | 6 |
| `test_ingest_species` | marker 入库 + 幂等回填 + event 写入 | 4 |
| `test_tools_species_compare` | 空菌株 / 单方法 / 多方法矩阵输出 | 3 |

## 7. 验收标准

1. `uv run pytest tests/unit/ -k "species or gom or download"` 全绿；全量 1415+ 测试无回归
2. `identify()` 旧调用方（species.smk、vpara 规则）零改动兼容（新增字段有默认值）
3. `setup_databases.py --tier mini --yes` 在空环境跑通（mini 档真实下载 RefSeq 面板——若 A 未就绪则以 stub 清单演练框架）
4. 存量 gold standard 样本 `--backfill-species` 后，每株 GOM 有 marker 对象且 `bio_species_compare` 可查询
5. mypy strict / ruff 零新增违规

## 8. 风险

| 风险 | 缓解 |
|---|---|
| `_validate_analysis_payload` 重命名影响 cgMLST 测试 | 保留旧函数名作 alias 或同步改测试引用（改动面小，grep 确认） |
| 下载源国内不可达 | 框架层镜像+代理已设计；各库至少给 2 个源（详见各分计划） |
| marker 回填的 database.version 用 sha256 前 8 位与现有 markers.fasta 命名不一致 | 统一规则写入 manifest，全库沿用 |
