# 更新日志 Changelog

完整变更记录见项目根目录 [CHANGELOG.md](../../CHANGELOG.md)。

## 版本概览

| 版本 | 主题 | 关键更新 |
|---|---|---|
| **V0.1** | Salmonella MVP | `invA` 物种鉴定、SISTR 血清型、gmlst MLST、abricate AMR/毒力/质粒扫描 |
| **V0.2** | DEC + Shigella 扩展 | `uidA` / `ipaH` 双靶基因、`ecoh_serotyper`、ShigATyper 移植 58 种血清型、pathotype 判定 |
| **V0.3** | SNP + 系统发育 | Salmonella LT2 参考基因组、`bwa` + `bcftools` + `IQ-TREE` 全基因组 SNP 树、暴发阈值 |
| **V0.4** | 物种统一与架构精简 | `species_identifier.py` 合并 4 rule 为 1 次 BLAST、`gene_scanner` 通用引擎、血清型分流逻辑 |
| **V0.5** | 引擎 + 注释 + Web UI + LLM | 原生基因组注释 (`pyrodigal` + Prokka DBs)、HTML 报告、Hermes 17 tools、LLM 自动解读 |

## 各版本要点

### V0.1 Salmonella MVP

- 建立以 `invA` 为靶基因的物种鉴定体系
- 集成 SISTR 血清型预测与 gmlst `salmonella_2` MLST
- 使用 abricate 扫描 CARD、VFDB、PlasmidFinder

### V0.2 DEC + Shigella

- 新增 `uidA`（E. coli/DEC）与 `ipaH`（Shigella/EIEC）靶基因
- 完成三基因交叉验证矩阵（无交叉反应）
- 新增 `call_pathotype.py` 判定 STEC/EPEC/EIEC/ETEC/EAEC

### V0.3 SNP Phylogenetics

- 引入 NC_003197.2 LT2 参考基因组
- 构建 joint VCF → SNP matrix → IQ-TREE 流程
- 定义 0–5 SNPs 同暴发阈值

### V0.4 架构精简

- `species_markers.fasta` 统一物种鉴定
- `gene_scanner` 替代重复 BLAST 逻辑
- `collect_summary.py` 自动选择 primary serotype

### V0.5 智能化升级

- `genome_annotator.py` 原生注释，预期 ~4500 CDS、75% 注释率
- HTML 报告整合 verifier 证据链
- 17 个 Hermes tools 支持自然语言交互

## 当前状态

- 支持 4 种食源性病原：Salmonella、DEC、Shigella/EIEC、V. parahaemolyticus
- 端到端 Snakemake 管线 + GOM 入库 + HTML 报告
- 10/10 株 gold standard 全量验证

> 完整详情、PR 链接与未发布改动请查阅 [CHANGELOG.md](../../CHANGELOG.md)。
