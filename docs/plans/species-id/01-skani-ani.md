# 方案 A · skani ANI 物种鉴定（三档数据库）

前置：P0 · 估算：7-8 人日 · 交付后 `species_mode: panel | skani_gtdb | mash_refseq` 全部可用

## 1. 定位

用**真 ANI 算法**（GTDB-Tk v2.4+ 内部同款）补齐方法学覆盖。skani 对碎片化 draft 组装稳健（Nature Methods 2023），官方预 sketch 库查询 >14 万物种代表株仅需秒级 + <30GB RAM。三档数据库满足不同部署条件：

| 档 | species_mode | 数据库 | 体积 | 来源（已核实） |
|---|---|---|---|---|
| A-mini | `panel` | NCBI RefSeq 策展精选面板 → 本地 `skani sketch` | 1-2 GB | `assembly_summary_refseq.txt` 的 `refseq_category` 过滤 |
| A-full | `skani_gtdb` | skani 官方预 sketch GTDB R226（>140k 代表株） | 30 GB 压缩 / 50 GB 解压 | CMU：`faust.compbio.cs.cmu.edu/skani-files/skani_gtdb_r226-v0.3.tar.gz` |
| A-instant | `mash_refseq` | 社区自动维护 Mash sketch（RefSeq v237） | 159 MB | Zenodo：`zenodo.org/records/22664519` |

## 2. 交付物清单

| 文件 | 类型 | 内容 |
|---|---|---|
| `pixi.toml` | 修改 | `skani = "0.3.*"`（**锁版本**：官方库 sketch 格式 v0.3，GTDB-Tk 亦锁 0.3.1）+ `mash = ">=3"` |
| `src/hermes_bacmap/engine/backends/skani.py` | 新增 | SkaniBackend：`search(query, db) -> list[AniHit]`（ANI + aligned_fraction） |
| `src/hermes_bacmap/engine/backends/kmer.py` | 修改 | MashBackend 增加 `search_top(query, msh) -> list[KmerDistance]`（按 identity 排序） |
| `src/hermes_bacmap/engine/__init__.py` + `registry.py` | 修改 | 注册 skani 后端，`available()` 探测 |
| `src/hermes_bacmap/analysis/ani_identifier.py` | 新增 | `identify_by_ani(contigs, mode) -> SpeciesIdResult`：调 engine 后端，阈值判定 + top_hits 裁剪 |
| `workflows/bacmap/rules/species.smk` | 修改 | 按 `species_mode` 分派：`species_ani` rule（panel/skani_gtdb → skani；mash_refseq → mash） |
| `scripts/download_db_refseq_panel.py` | 新增 | A-mini 面板构建（§4.1） |
| `scripts/download_db_skani_gtdb.py` | 新增 | A-full 下载（§4.2） |
| `scripts/download_db_mash_refseq.py` | 新增 | A-instant 下载（§4.3） |
| `scripts/ingest_results.py` | 修改 | ANI 结果入库（method=panel/skani_gtdb/mash_refseq） |
| `src/hermes_bacmap/skills/bio-router/SKILL.md` | 修改 | 路由决策树：何时建议升级 ANI 档位 |
| `tests/unit/test_ani_identifier.py` 等 | 新增 | §7 |

## 3. 核心设计

### 3.1 判定逻辑（ani_identifier.py，三档共用）

```
top_hit = max(hits, key=(ani, aligned_fraction))
判定：
  ani ≥ 95.0 且 af ≥ 0.65        → species = top_hit 物种, confidence = high
  95.0 > ani ≥ 93.0              → species = top_hit 物种, confidence = medium（边界区）
  ani < 93.0 或 af < 0.65        → species = "Unknown", confidence = low, 保留 top_hits 供人审
```

依据：95-96% ANI 为原核物种界标准阈值（Goris 2007 / Richter 2009）；AF 阈值防低覆盖偶然命中。**边界区（93-95%）单列 medium 档**而非直接判种——近缘种（V. alginolyticus vs V. parahaemolyticus）可能落入此区，交给仲裁层。

top_hits 取前 10 名（含 accession、物种名、ANI、AF），全量入 GOM `result.top_hits`，便于比较与审计。

### 3.2 物种名映射

skani GTDB 库的 reference ID 是 GTDB accession（`GCF_...`）→ 需要 `skani_gtdb` 档附 taxonomy 映射。官方 tar.gz 内含基因组 FASTA 索引；下载脚本额外抓取 GTDB `bac120_taxonomy_r226.tsv`（~80MB）建 `accession → GTDB 物种名` 查找表，再映射到四病原内部命名。
**Shigella 在 GTDB 里并入 E. coli**——映射表显式标注 `expected_divergence`，衔接 P0 仲裁豁免。

mini 面板自带物种名（下载脚本生成 metadata.tsv），无需外部映射。

### 3.3 Snakemake 接入

`species.smk` 保持现有 `species_identify`（marker 恒跑，作对照与降级兜底），新增：

```python
rule species_ani:
    input: contigs = .../contigs.fasta
    output: result = .../species/species_ani.json
    params: mode = config["species_mode"]  # panel | skani_gtdb | mash_refseq
    shell: "<pixi python> -c 'ani_identifier 主入口' || echo '<fallback>'"
```

`config.species_mode ∈ {panel, skani_gtdb, mash_refseq}` 时 `rule all` 追加该输出；`report.smk` 的 `report_summary` 输入列表同步扩展（marker + ANI 双字段）。

## 4. 三个下载脚本

### 4.1 download_db_refseq_panel.py（A-mini，最复杂）

数据源策略——**NCBI 已完成策展，我们只做分类群过滤**：

1. 下载 `assembly_summary_refseq.txt`（229MB，FTP）
2. 过滤：`refseq_category ∈ {reference genome, representative genome}` **且** organism 属于目标分类群清单：
   - 目标病原：*Salmonella enterica*、*Escherichia coli*（含 Shigella 同物异名）、*Vibrio parahaemolyticus*
   - 近缘对照：*V. alginolyticus / V. harveyi / V. vulnificus / V. cholerae*、*Klebsiella* spp.、*Enterobacter / Cronobacter / Citrobacter*、*Listeria / Campylobacter*（食品安全常客）
   - 环境干扰：*Pseudomonas / Bacillus / Staphylococcus* 代表株各 1-2 株
3. 每物种上限 N（默认 5 株，reference 优先），总量预期 300-500 株
4. `ncbi-datasets-cli`（**已安装**）按 accession 清单 dehydrate/rehydrate 批量下载 FASTA
5. `skani sketch panel/*fna -o data/db/refseq_panel/panel.sketch` + 生成 `metadata.tsv`（accession / 物种 / refseq_category / 内部分组）
6. manifest 落盘（含过滤规则快照 + assembly_summary 的日期，保证可复现）

分类群清单做成 `data/db/refseq_panel/taxa_filter.yaml` 配置——用户可自行增删物种重建。**可选增强**（本期不做）：叠加 NCBI Pathogen 目录代表株补充血清型多样性。

### 4.2 download_db_skani_gtdb.py（A-full）

```
URL: http://faust.compbio.cs.cmu.edu/skani-files/skani_gtdb_r226-v0.3.tar.gz
md5: 下载后与发布页核对；体积 30GB；解压 50GB；min_free_gb=110
附加: GTDB bac120_taxonomy_r226.tsv（data.gtdb.ecogenomic.org，3 个官方镜像按序尝试）
```

国内可达性未知 → 框架的 `--mirror` 必选项此库先行验证（CMU 源失败时提示用户配置代理或改用 mini/instant 档）。

### 4.3 download_db_mash_refseq.py（A-instant）

```
URL: https://zenodo.org/records/22664519/files/RefSeqSketches_237.msh.gz
md5: dee53b23af3ab120333f9eb1b95ae60f（v237）；159.4MB；解压后直接可用
维护: erinyoung/update_mash_dist，随 RefSeq release 自动更新——升级即重跑本脚本
```

定位：低配机器预筛与方法速查。**注意**：纯 sketch 法对不完整基因组 ANI 估计偏低（skani 论文实测 50% 完整度时偏差可达 4%），判定阈值放宽为 `identity ≥ 0.97`（Mash identity 与 ANI 的经验换算），且结论 confidence 上限 medium——鼓励冲突时升级到 skani 档复核。

## 5. GOM 集成

method 分别为 `panel` / `skani_gtdb` / `mash_refseq`；`database.name` 对应三库；`database.version`：panel 用 manifest 里的过滤快照日期、skani_gtdb 用 `R226`、mash 用 `RefSeq-237`。其余按 P0 共享 schema 填充。

## 6. Hermes 集成

- `bio_validate_taxonomy` 传 `method=panel|skani_gtdb|mash_refseq` → 即时对已有 contigs 重跑并入库（无需重跑管线）
- `bio-router` SKILL.md 决策树新增：marker 置信 low / 多 marker 冲突 / `expected_divergence` 需确认 → 建议用户 `bio_validate_taxonomy --method skani_gtdb`

## 7. 测试计划

| 测试 | 内容 | 数量 |
|---|---|---|
| `test_skani_backend` | 真实 skani 二进制（pixi 安装后）：组装 vs 面板 top_hit 正确性、输出解析 | 4 |
| `test_ani_identifier` | 阈值边界（95/93/AF 0.65）、medium 边界区、Unknown 保留 top_hits | 8 |
| `test_download_refseq_panel` | assembly_summary 解析过滤（fixture 小表）、taxa_filter.yaml 生效、上限 N | 5 |
| `test_download_skani_gtdb / mash` | 框架参数接线（md5/体积/镜像顺序），mock 下载 | 4 |
| `test_species_ani_rule` | snakemake --dry-run：mode 分派 + rule all 追加 | 3 |
| gold standard 验证 | 12 株三档全跑：panel/skani_gtdb 物种准确率 ≥99%；mash ≥95%（记录基线） | 1 harness |

## 8. 验收标准

1. `species_mode: skani_gtdb` 端到端：gold standard 株 ANI 鉴定正确、GOM 对象齐备、`bio_species_compare` 显示 marker+ANI 双方法矩阵
2. 三档下载脚本幂等重跑、md5 校验、manifest 完整
3. 数据库缺失时降级 simple 且 species_id.json 记录原因
4. pixi 锁定 skani 0.3.*，与官方库格式兼容（search 冒烟通过）
5. 全量测试无回归，mypy strict 零违规

## 9. 风险

| 风险 | 缓解 |
|---|---|
| CMU 源国内不可达 | --mirror + 代理透传；文档给出 mini 档替代路径 |
| GTDB taxonomy 映射与 NCBI 命名差异（Shigella 合并） | §3.2 显式映射表 + 仲裁豁免，gold standard 验证 |
| RefSeq 面板某近缘种缺少 reference genome | 过滤规则回退取 representative；再无则 taxa_filter 提示 |
| skani 版本升级破坏 sketch 格式 | pixi 锁 0.3.*；升级路径=重新下载官方库（跟随 GTDB-Tk 锁定节奏） |
