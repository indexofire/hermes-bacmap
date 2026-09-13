# 方案 C · GTDB-Tk + CheckM2 标准模式（金标准仲裁层）

前置：P0 · 估算：3-4 人日（代码已大半存在，本计划主要是供给、门禁与规范化） · 交付后 `species_mode: standard` 完整可用

## 1. 定位

`analysis/taxonomic_validator.py` 的 standard 模式已实现 GTDB-Tk + CheckM2 调用与优雅降级——本计划补齐的是**数据库供给、硬门禁、证据链规范与 GOM 入库**。定位为仲裁手段（marker 与 ANI 不一致、疑似新物种、监管复核），不作为常规监测选项。

**硬约束（必须前置声明）**：GTDB-Tk v2.7.2 + R232 数据库需要 **~140GB 可用内存**（细菌 classify），**超过 project.md 推荐档的 128GB**。安装器必须 RAM 硬门禁；舒适档（256GB）可运行。

## 2. 交付物清单

| 文件 | 类型 | 内容 |
|---|---|---|
| `pixi.toml` | 修改 | 新增 `[feature:taxonomic]` 环境：`gtdbtk = "2.7.*"`、`checkm2`（避免污染默认环境；`pixi run -e taxonomic`） |
| `src/hermes_bacmap/config.py` | 修改 | `GTDBDB` → `GTDBTK_DATA_PATH`（官方变量名；旧名保留读取作兼容） |
| `src/hermes_bacmap/analysis/taxonomic_validator.py` | 修改 | 结果结构对齐 P0 共享 schema（method=gtdbtk、database、result.top_hits）；CheckM2 完整度/污染度并入 payload |
| `scripts/download_db_gtdbtk.py` | 新增 | R232 数据包下载（§4.1） |
| `scripts/download_db_checkm2.py` | 新增 | DIAMOND 库下载（§4.2） |
| `scripts/ingest_results.py` | 修改 | standard 结果入库（taxonomy + 质量双 payload） |
| `docs/installation/local-llm.md` 或新页 | 修改/新增 | 标准模式硬件门槛专页（140GB RAM / 220GB 磁盘 / 预计时长） |
| `tests/unit/test_taxonomic_validator_ext.py` | 修改 | 新增门禁与 schema 测试 |

## 3. 核心设计

### 3.1 执行流程（沿用现有 validate_genome，规范化输出）

```
CheckM2 predict --input contigs.fasta --database_path $CHECKM2DB     → completeness / contamination
GTDB-Tk classify --genome_dir <dir> --align_dir ... --cpus N         → GTDB 分类 + FastANI 最优参考
（GTDBTK_DATA_PATH 指向 R232；pplacer 步骤耗时数分钟—30 分钟，单株可接受）
```

判定：GTDB species rank 明确 → confidence=high（金标准）；仅在 genus rank → medium + 建议人工复核。`result.top_hits` 填 GTDB 报告的最近参考基因组与 ANI。
**CheckM2 输出（完整度/污染度）独立于物种结论**，作为质量信号写入同对象 payload（`result.quality`），污染度 >5% 时置 `NEEDS_REVIEW`。

### 3.2 RAM 与磁盘硬门禁（下载脚本层）

`download_db_gtdbtk.py` 调用 P0 框架时：`min_ram_gb=140`（读 `/proc/meminfo` MemAvailable，不足**硬拒绝**并提示舒适档硬件或改用 A/B 档）；`min_free_gb=220`（98GB tar + 98GB 解压 + pplacer 临时空间）。
下载后自动 `tar` + 提示设置 `GTDBTK_DATA_PATH`，并写入用户 shell 配置建议（不静默改 shell）。

### 3.3 Shigella/E.coli 处理

GTDB 将 Shigella 归入 *E. coli*——validator 映射表标注 `expected_divergence`（同 P0 豁免规则），不触发冲突告警。

## 4. 下载脚本

### 4.1 download_db_gtdbtk.py

```
源（按序，均官方）:
  1. https://data.gtdb.aau.ecogenomic.org/releases/release232/232.0/auxillary_files/gtdbtk_package/full_package/gtdbtk_r232_data.tar.gz
  2. https://data.gtdb.ecogenomic.org/releases/... (Australia 镜像)
  3. https://data.ace.uq.edu.au/public/gtdb/data/releases/... (Australia 镜像)
md5: 25a59e0352b1fd150c589f56559767d4（官方表，R232）
体积: ~98GB 下载 / ~98GB 解压；min_ram_gb=140, min_free_gb=220
版本兼容: gtdbtk>=2.7.0（R232）；manifest 记录 gtdbtk 版本上限
```

### 4.2 download_db_checkm2.py

```
优先: checkm2 database --download --path data/db/checkm2/（工具自带，feature 环境安装后可用）
兜底: https://zenodo.org/record/14897628 (uniref100.KO.1.dmnd, ~3GB)
环境变量: CHECKM2DB 指向 .dmnd 文件（config.py 已支持）
```

## 5. GOM 集成

method=`gtdbtk`；`database.name=gtdbtk_r232`；`result` 含 GTDB 全 lineage、最近参考、ANI、`quality: {completeness, contamination}`。CheckM2 单独失败不阻断 GTDB-Tk 结果入库（分对象记录降级原因）。
standard 模式同时照跑 marker（对照）→ 同株双对象，`bio_species_compare` 直接可见金标准 vs 快速方法差异。

## 6. 测试计划

| 测试 | 内容 | 数量 |
|---|---|---|
| `test_gtdbtk_download_gate` | RAM/磁盘门禁拒绝路径（monkeypatch meminfo / statvfs） | 4 |
| `test_taxonomic_standard_schema` | payload 必填校验、expected_divergence 标注、quality 并入 | 5 |
| `test_ingest_gtdbtk` | 双对象（marker+gtdbtk）并存 + event | 3 |
| gold standard（有库环境手动跑） | 12 株 GTDB 分类正确 + CheckM2 完整度 >95% | 1（标记 skip-if-no-db） |

CI 策略：GitHub Actions 不下载 98GB 库——standard 路径全部 mock 测试；真实库验证在本地文档化流程执行（validate_analytical.py 加 `--method standard --skip-if-no-db`）。

## 7. 验收标准

1. 舒适档机器：`species_mode: standard` 端到端单株跑通（CheckM2 + GTDB-Tk + GOM 双对象）
2. 推荐档（128GB）机器：下载脚本**硬拒绝**并给出替代建议；管线 standard 模式优雅降级 simple
3. `GTDBTK_DATA_PATH` 环境变量全链路一致（config.py → rule → subprocess）
4. 全量测试无回归（CI 无库环境全绿）

## 8. 风险

| 风险 | 缓解 |
|---|---|
| R232 后续版本体积再涨 | manifest 记录版本；文档注明升级=重新下载（官方每版不兼容） |
| pplacer 单株 30 分钟拖慢批处理 | 文档明示 standard 定位为按需仲裁而非批处理；96 株批跑不建议 standard |
| pixi feature 环境与 Hermes venv 冲突 | gtdbtk 仅 Snakemake 子进程调用，不进 Hermes 插件依赖 |
