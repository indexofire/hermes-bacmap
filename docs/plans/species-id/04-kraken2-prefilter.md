# 方案 D · Kraken2 reads 层预筛（污染告警 + 去人源）

前置：P0（依赖 A-mini 面板，最佳实施顺序与 A 并行） · 估算：4-5 人日 · 交付后 `kraken2_prefilter: true` 可用

## 1. 定位

Kraken2 在 **reads 层**（组装之前）做分类预筛，与物种鉴定模式（contigs 层）正交，独立开关、可与任何 species_mode 组合。两个价值：

1. **最早告警**：混合样本/污染在消耗 SPAdes 算力之前发现；Bracken 丰度定量给出非目标物种构成
2. **去人源（合规）**：数据库含 GRCh38 + UniVec，classified human/vector 读段剔除后，干净的 unclassified reads 进入 fastp/组装——公卫场景人源序列剔除有人类遗传资源管理与样本隐私的合规意义

先例：Bactopia 的 kraken2 模块（reads 分类 + host scrubbing）。

## 2. 交付物清单

| 文件 | 类型 | 内容 |
|---|---|---|
| `pixi.toml` | 修改 | `kraken2 = ">=2.1"`、`bracken = ">=2.9"` |
| `workflows/bacmap/rules/qc.smk` | 修改 | 新 rule `kraken2_prefilter`（raw reads → 分类报告 + clean reads） |
| `workflows/bacmap/scripts/kraken2_report.py` | 新增 | 解析 kraken2 report + bracken 输出 → `kraken2_prefilter.json`（构成 + 人源比例 + 告警 flags） |
| `scripts/download_db_kraken2.py` | 新增 | 自建库（§4） |
| `workflows/bacmap/config/config.yaml` | 修改 | `kraken2_prefilter: {enabled: false, human_scrub: true, alert_threshold: 0.05}` |
| `scripts/ingest_results.py` | 修改 | method=kraken2 结果入库 |
| `tests/unit/test_kraken2_prefilter.py` 等 | 新增 | §6 |

## 3. 核心设计

### 3.1 流程位置（fastp 之前）

```
raw R1/R2 ──► kraken2 --db <custom> --paired --out-fq clean_R1 clean_R2 (unclassified 输出)
                 │                    │
                 ├─ report ◄──────────┤ human_scrub=true: 剔除 classified(human/vector) 读段
                 └─ bracken -k 35 -l S ──► species 丰度表
clean reads ──► fastp（现有 qc_fastp，输入路径由开关切换）
```

- `human_scrub: false` 时 kraken2 仅报告不剔除（fastp 照常吃 raw reads）
- 剔除比例 >10% 时在 JSON 打 `high_host_content` flag（提示送样问题）
- 非目标物种合计丰度 >5%（`alert_threshold`）→ `off_target_species` flag + top 5 物种清单——**培养污染/错管最早告警**

### 3.2 判定输出（kraken2_report.py）

```json
{
  "method": "kraken2",
  "result": {
    "species": "<目标物种或 Off-target>",
    "confidence": "high|medium|low",
    "top_hits": [{"species": "...", "abundance_pct": 97.2, "reads_assigned": 1234567}],
    "host_reads_removed_pct": 1.3,
    "flags": []
  }
}
```

物种判定：与样本表声明物种一致且丰度 ≥90% → high；50-90% → medium（混合嫌疑）；<50% → Off-target + NEEDS_REVIEW。kraken2 结果同样走 GOM（method=kraken2），进 `bio_species_compare` 矩阵——reads 层与 contigs 层方法的一致性首次可横向审计。

## 4. 自建数据库（download_db_kraken2.py）

Kraken2 无适用的官方预建小库（standard ~100GB / minikraken2 内容陈旧），**自建**：

```
1. 基因组来源（全部已有或复用）：
   - 病原面板：复用 A-mini 的 RefSeq 精选面板 FASTA（download_db_refseq_panel.py --fastas-only 输出）
   - 人类：GRCh38 主要分析集 FASTA（NCBI，~3GB，--mirror 支持）
   - 载体：kraken2-build --download-library UniVec_Core
2. 构建：
   kraken2-build --download-taxonomy --db data/db/kraken2_custom
   kraken2-build --add-to-library ...（逐组添加，物种命名与面板 metadata.tsv 对齐）
   kraken2-build --build --kmer-len 35 --minimizer-len 31 --threads 32
   bracken-build -d data/db/kraken2_custom -k 35 -l 150
3. 预期体积：~5-6 GB（300-500 株细菌 + 人 + UniVec）
4. manifest 记录面板版本（与 A-mini 联动）+ GRCh38 版本 + build 参数
```

构建耗时参考：该规模分钟级（远小于全库的 24h+ 级）。**库随面板升级**：重跑 A-mini 脚本 + 本脚本即可（幂等重建）。

## 5. GOM 与 Hermes 集成

- GOM：method=kraken2，`database.name=kraken2_custom`，version 引用面板 manifest；result 含丰度表与人源剔除统计
- Hermes：`bio_validate_taxonomy --method kraken2` 不适用（reads 层），改为 `bio_diagnose` 消化 `off_target_species` flag；`bio-router` 决策树加：prefilter 告警 → 建议停止批处理该株并人工核查

## 6. 测试计划

| 测试 | 内容 | 数量 |
|---|---|---|
| `test_kraken2_report` | report/bracken 解析、丰度阈值三档判定、双 flag 触发 | 8 |
| `test_kraken2_rule` | dry-run：开关启停对 DAG 的影响、fastp 输入切换 | 3 |
| `test_download_kraken2` | 面板复用逻辑（--fastas-only 联动）、taxonomy 构建 mock | 3 |
| 集成（有库环境） | gold standard 株 reads：判定正确 + 人为掺入 5% 大肠杆菌 reads 检出 off_target | 2 |

## 7. 验收标准

1. `kraken2_prefilter.enabled=true` 端到端：clean reads 进入 fastp，prefilter JSON 入 GOM，比对矩阵含 reads 层方法
2. 掺混实验：目标物种 95% + 掺入 5% 近缘种 → `off_target_species` flag 检出
3. human_scrub 开关行为正确，剔除比例统计准确
4. 全量测试无回归（无库环境 mock 全绿）

## 8. 风险

| 风险 | 缓解 |
|---|---|
| reads 级 LCA 特异性低于组装级（近缘种误分） | 阈值保守（90% high），与 contigs 层方法互证而非单独定论 |
| 人源剔除影响下游覆盖度 | 剔除比例统计入 JSON，>10% 告警；fastp 前后 QC 指标对照可查 |
| 自建库随面板漂移 | manifest 版本联动 + 幂等重建；面板更新文档注明需重建 kraken2 库 |
| GRCh38 下载体积与国内可达性 | --mirror（NCBI HTTPS / Ensembl 镜像）+ 断点续传 |
