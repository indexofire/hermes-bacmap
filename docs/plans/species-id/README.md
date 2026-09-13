# 物种鉴定多方法体系开发计划（V0.8 专项）

状态：计划评审中 · 起草日期：2026-09-12 · 依赖调研：见 `docs/plans/species-id/` 各分计划

本专项实现**五种物种鉴定方法并存、用户自选**的完整体系，并落实两项横切要求：

1. **鉴定方法与结果写入 GOM、跟随菌株**：每种方法的每次鉴定结果都是独立 ANALYSIS 对象（Immutable、INSERT-ONLY），多方法并存不覆盖，支持按菌株横向比较与方法间一致性审计。
2. **每个数据库独立下载脚本**：`scripts/download_db_<name>.py` 一库一脚本，统一走公共下载框架（体积预检 / md5 校验 / 断点续传 / 镜像参数 / manifest 落盘），安装期由 `setup_databases.py` 交互式编排。

## 分计划索引

| 编号 | 文档 | 方案 | 核心交付 | 建议排期 |
|---|---|---|---|---|
| P0 | [00-foundation.md](00-foundation.md) | 共享地基 | GOM schema 扩展、species_mode 统一、下载脚本框架、marker 方法 GOM 回填 | 第 1-2 周 |
| A | [01-skani-ani.md](01-skani-ani.md) | skani ANI（三档） | panel / skani_gtdb / mash_refseq 三种模式 + 对应下载脚本 | 第 2-4 周 |
| B | [02-sourmash.md](02-sourmash.md) | sourmash 广谱 + gather | sourmash 模式 + 混合样本分解 | 第 4-5 周 |
| C | [03-gtdbtk-checkm2.md](03-gtdbtk-checkm2.md) | GTDB-Tk + CheckM2 仲裁 | standard 模式供给补全 + RAM 硬门禁 | 第 5-6 周 |
| D | [04-kraken2-prefilter.md](04-kraken2-prefilter.md) | reads 层预筛 + 去人源 | kraken2_prefilter 独立开关 + 合规价值 | 第 2-4 周（与 A 并行） |

## 五方法总览

| 方法 | species_mode | 输入层级 | 数据库 | 体积 | 单株耗时 | 定位 |
|---|---|---|---|---|---|---|
| 靶基因（现有） | `simple` | contigs | species_markers.fasta | 0（已有） | 秒级 | 默认快速路由 |
| skani 面板 ANI | `panel` | contigs | RefSeq 精选面板（NCBI 策展） | 1-2 GB | 秒级 | A-mini，定向 ANI |
| skani GTDB 全库 | `skani_gtdb` | contigs | skani 官方预 sketch GTDB R226 | 30 GB | 秒级 | A-full，广谱真 ANI |
| Mash RefSeq sketch | `mash_refseq` | contigs/reads | 社区自动维护 sketch（Zenodo） | 159 MB | 秒级 | A-instant，低配预筛 |
| sourmash gather | `sourmash` | contigs | sourmash 官方 GTDB 签名 | 3.7 GB | 秒级 | 广谱 + 混合样本分解 |
| GTDB-Tk + CheckM2 | `standard` | contigs | GTDB R232 + CheckM2 | 98 GB + 3 GB | 分钟-小时级 | 金标准仲裁 |
| Kraken2 预筛 | 独立开关 | **reads** | 自建（面板 + GRCh38 + UniVec） | ~5 GB | 分钟级 | 组装前告警 + 去人源 |

> Kraken2 与其余方法**不同维度**（reads vs contigs），不占用 species_mode 枚举，独立配置开关，可与任何模式组合。

## 共享设计约定（各分计划必须遵守）

### GOM 物种鉴定对象（P0 定义，各方法填充）

沿用 cgMLST 的 `analysis_type` 校验模式（`genome_object_service.py` 的 `_CGMLST_REQUIRED_FIELDS` 先例），新增：

```json
{
  "object_type": "analysis",
  "strain_id": "SAM-TYP-001",
  "payload": {
    "analysis_type": "species_identification",
    "method": "marker | panel | skani_gtdb | mash_refseq | sourmash | gtdbtk | kraken2",
    "tool_versions": {"skani": "0.3.1"},
    "database": {"name": "skani_gtdb_r226", "version": "R226", "manifest": "data/db/manifests/skani_gtdb.json"},
    "result": {
      "species": "Salmonella enterica",
      "confidence": "high",
      "ani": 98.7,
      "aligned_fraction": 0.92,
      "top_hits": [{"genome": "GCF_...", "ani": 98.7, "af": 0.92}]
    },
    "sample_declared_species": "Salmonella",
    "agreement": {"status": "match|conflict|n/a", "compared_methods": ["marker"]}
  },
  "pipeline_version": "<rule 或工具版本>",
  "database_signature": "skani_gtdb_r226@R226"
}
```

- **必填字段**（GOM 校验）：`method`、`database`、`result`；`result.species`、`result.confidence` 必填，方法特有字段可选
- **多方法并存**：每方法每版本一个独立对象，`(object_id, version)` 复合主键保证 Immutable；重跑生成新 object_id
- **跟随菌株比较**：按 `strain_id + payload.analysis_type` 聚合查询 → `bio_species_compare` 工具输出方法一致性矩阵
- **新增 EventType**：`species_identified`（写入 events 表，Event First 原则）

### 仲裁规则（deterministic_verifier 扩展）

优先级 `gtdbtk > skani_gtdb/panel/sourmash/mash_refseq > marker`；同层方法结论冲突（如 marker=Shigella、skani=E.coli，生物学上必然发生）→ 打 `NEEDS_REVIEW` 标记走人审，禁止静默择一。Shigella/EIEC 同种情形单独处理：skani/gtdbtk 层面判定为 *E. coli* 复合群属正常，不触发冲突。

### 下载脚本框架（P0 实现，各脚本复用）

```
scripts/
├── _common.py                    # + 下载公共函数（见 00-foundation.md）
├── setup_databases.py            # 交互式 tier 编排器（薄壳，调下列脚本）
├── download_db_refseq_panel.py   # A-mini：NCBI RefSeq 策展面板
├── download_db_skani_gtdb.py     # A-full：skani 官方 GTDB R226（CMU 源）
├── download_db_mash_refseq.py    # A-instant：社区 Mash sketch（Zenodo）
├── download_db_sourmash_gtdb.py  # B：sourmash GTDB 签名（UC Davis 源）
├── download_db_gtdbtk.py         # C-1：GTDB-Tk R232（含 140GB RAM 预检）
├── download_db_checkm2.py        # C-2：CheckM2 DIAMOND 库（Zenodo）
└── download_db_kraken2.py        # D：自建（复用面板 + GRCh38 + UniVec）
```

每个脚本必须实现：体积与磁盘预检、md5/sha256 校验、断点续传（`wget -c` 或 Range 请求）、`--mirror` 参数（国内可达性适配）、幂等（已存在且校验通过则跳过）。
manifest JSON 落盘（`data/db/manifests/<name>.json`：库名、版本、下载日期、源 URL、校验和、文件清单）——manifest 供 GOM `database_signature` 与三元证据链引用。

### 环境变量与配置对齐（P0）

- `config.py`：`GTDBDB` → `GTDBTK_DATA_PATH`（GTDB-Tk 官方变量名）；`CHECKM2DB` 已一致，保留
- `config.yaml`：`species_mode: simple|panel|skani_gtdb|mash_refseq|sourmash|standard` + `kraken2_prefilter: false`
- CLI：`run_analysis.py --species-mode`；Hermes tool：`bio_validate_taxonomy` 增加 `method` 参数透传

### pixi 依赖（各方案分计划明细）

skani（**锁 0.3.x**，与官方预 sketch 库格式兼容）、kraken2 + bracken、mash（注意：README 环境表声称已含 mash，实际 pixi.toml 没有——本专项补齐并修 README）。
gtdbtk + checkm2 建议放 pixi feature 环境 `[feature:taxonomic]` 避免污染默认环境。`ncbi-datasets-cli` 已安装（≥16），面板下载直接复用。

## 排期与依赖

```
P0 地基（GOM + 开关 + 下载框架）      ██░░░░░░░░  第 1-2 周
A skani 三档（panel→full→instant）     ░░███░░░░░  第 2-4 周（依赖 P0）
D Kraken2 预筛（与 A 并行，共用面板）   ░░███░░░░░  第 2-4 周（依赖 P0 面板）
B sourmash 模式                       ░░░░░██░░░  第 4-5 周（依赖 P0）
C GTDB-Tk 供给 + 门禁                 ░░░░░░░██░  第 5-6 周（依赖 P0）
```

总量估算：约 25-30 人日（含测试与文档）。

## 验收总标准（各分计划有细化）

1. 同一株用 ≥3 种方法鉴定，GOM 中并存 ≥3 个 species_identification 对象，`bio_species_compare` 输出一致性矩阵
2. 每个对象的 `database_signature` 可追溯到 manifest 文件与下载源
3. gold standard 12 株：五方法物种鉴定准确率 ≥99%（marker 已达标；新方法以此为基线）
4. 任一数据库缺失时管线优雅降级（回退 simple 并记录原因），不中断
5. `setup_databases.py` 安装任意 tier 后对应模式可直接运行，全程无需手动干预
