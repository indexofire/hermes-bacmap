# 方案 B · sourmash GTDB 广谱鉴定与混合样本分解

前置：P0（A 非硬依赖，可并行） · 估算：4 人日 · 交付后 `species_mode: sourmash` 可用

## 1. 定位

sourmash 已是 pyproject 依赖（≥4.8），engine 的 kmer 后端已有 MinHash 基础。本方案的独特价值**不是广谱覆盖**（A-full 已覆盖），而是 `gather` 的**最小集合覆盖分解**——对混合样本/污染给出基因组级拆解（哪些参考基因组以多少 containment 覆盖了查询的 k-mer 空间），这是 skani search 不具备的能力。
推荐流程为官方 2023 后的 `gather` + `tax genome` 两步（弃用易误报的 lca 模块）。

## 2. 交付物清单

| 文件 | 类型 | 内容 |
|---|---|---|
| `src/hermes_bacmap/analysis/sourmash_identifier.py` | 新增 | `identify_by_sourmash(contigs) -> SpeciesIdResult`：sketch → gather → tax genome |
| `src/hermes_bacmap/engine/backends/kmer.py` | 修改 | SourmashBackend 增加 `gather(query_sig, db, taxonomy) -> GatherResult`（含 Python API 调用优先、CLI 兜底） |
| `workflows/bacmap/rules/species.smk` | 修改 | `species_sourmash` rule（mode=sourmash 分派） |
| `scripts/download_db_sourmash_gtdb.py` | 新增 | 官方签名库 + lineage 下载 |
| `scripts/ingest_results.py` | 修改 | method=sourmash 入库（含 gather 分解结果） |
| `tests/unit/test_sourmash_identifier.py` 等 | 新增 | §6 |

## 3. 核心设计

### 3.1 鉴定流程

```
sourmash sketch dna -p k=31,scaled=1000 contigs.fasta
sourmash gather query.sig gtdb-rs226-k31.dna.zip -o gather.csv      # 最小集合覆盖
sourmash tax genome --gather-csv gather.csv --taxonomycsv lineages.csv -o tax.csv
```

判定（保守，与 A 档阈值对齐）：

- top 基因组 `f_unique_weighted ≥ 0.90` 且 lineage 物种明确 → `confidence = high`
- `0.70-0.90` → `medium`（含混合嫌疑）
- top 覆盖 <0.70 或 gather 报告多个 ≥0.10 的组分 → `species = "Mixed/Unknown"`，**保留完整 gather 分解表**入 GOM（`result.gather_partition`：各参考基因组 + containment 丰度）——这是污染检测的直接证据

### 3.2 混合样本判定

gather 分解出 ≥2 个不同属的组分且各自 containment ≥0.10 → 额外输出 `result.flags = ["possible_mixture"]`，`agreement` 置 conflict 并 NEEDS_REVIEW（衔接 P0 仲裁）。对纯培养分离株，此 flag 出现即提示培养污染或错管——比组装后才发现（组装质量异常）提前一步。

### 3.3 GOM schema 扩展字段

method=sourmash 时 `result` 增加：`f_unique_weighted`、`gather_partition`（列表：genome / lineage / f_unique_weighted）、`flags`。其余按共享 schema。

## 4. 数据库与下载脚本

`download_db_sourmash_gtdb.py`：

```
主库: https://farm.cse.ucdavis.edu/~ctbrown/sourmash-db.new/gtdb-rs226/gtdb-reps-rs226-k31.dna.zip   (3.7 GB)
分类: https://farm.cse.ucdavis.edu/~ctbrown/sourmash-db.new/gtdb-rs226/gtdb-rs226.lineages.csv
备选镜像: 官方文档页列出的 OSF 历史版本（rs207 等，仅作 --mirror 兜底）
参数: min_free_gb=10；zip 可直接使用（无需解包，节省磁盘）
版本: RS226 写入 manifest 与 database_signature
```

选 reps（物种代表株，66k+）而非全库（21GB）：reps 对分离株鉴定足够，全库只对极近缘菌株区分有增益。

## 5. Hermes 集成

- `bio_validate_taxonomy --method sourmash`
- `bio-router` 决策树：疑似混合样本（组装覆盖度异常 / marker 多物种信号）→ 建议 sourmash gather 复核

## 6. 测试计划

| 测试 | 内容 | 数量 |
|---|---|---|
| `test_sourmash_identifier` | 高/中/混合三档判定、f_unique_weighted 阈值边界、gather_partition 结构 | 8 |
| `test_download_sourmash` | 框架接线、zip 直用不强制解压、lineages.csv 校验 | 3 |
| `test_species_sourmash_rule` | dry-run 分派 + rule all 追加 | 2 |
| gold standard | 12 株准确率 ≥95%（MinHash 近似，基线允许低于 skani）+ 人为混两株验证 mixture 检出 | 1 harness |

## 7. 验收标准

1. `species_mode: sourmash` 端到端可用，GOM 对象含 gather 分解
2. 人为混合样本（gold standard 两株 reads 按比例合并）→ `possible_mixture` flag 检出
3. 下载脚本幂等、manifest 完整、zip 直用
4. 全量测试无回归

## 8. 风险

| 风险 | 缓解 |
|---|---|
| MinHash 对碎片化组装 containment 偏低 | 分离株组装完整度高（Shovill），阈值已保守；文档注明局限 |
| UC Davis 源国内不可达 | --mirror + OSF 兜底 |
| sourmash 版本 API 变动（Python API 调用） | 优先 CLI 子进程（版本稳定面更大），Python API 仅作加速可选 |
