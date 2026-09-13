# 物种 marker 交叉反应判读

适用范围：marker 靶基因物种鉴定（species_mode=simple）的结果解读。AI 层在报告 marker 结果时必须应用本判读规则。

## 置信度分级（species_identifier 实现）

| 最佳命中 identity | confidence | 判读要求 |
|---|---|---|
| ≥ 90% | high | 可直接采信 |
| 85–90% | medium | **必须建议 ANI 复核**（`bio_validate_taxonomy --method skani_gtdb` 或 mash_refseq） |
| < 85% | 不命中 | — |

## 近缘守卫（硬规则）

`tlh` 单基因命中且 identity < 90% 时，物种判定**抑制为 Unknown**，notes 携带复核建议。依据：V. alginolyticus 等近缘种携带 tlh 同源基因（实测 85.2% 边缘命中案例，见 docs/cases/species-crossreaction.md）。

## 已知交叉反应清单

| marker | 近缘干扰源 | 实测数据 | 处置 |
|---|---|---|---|
| tlh | *V. alginolyticus*（tlh 同源基因） | identity 85.2% / coverage 86% → 误判 V.para | 守卫抑制 + ANI 复核 |
| toxR | *V. alginolyticus*（toxR 同源） | 实测 < 85% 不命中（E110 株） | 阈值天然过滤；85-90% 区间降 medium |
| invA / uidA / ipaH | 暂无实测误报 | — | 常规分级 |

## 判读话术模板

- medium 命中："`{gene}` 命中 identity `{x}%`（85-90% 边缘区），建议 ANI 全基因组复核确认物种。"
- 守卫触发："`tlh` 边缘命中（`{x}%`）可能是近缘弧菌（如 *V. alginolyticus*）同源基因，已抑制物种判定；请运行 ANI 复核。"

## 仲裁衔接

marker 结果与 ANI/GTDB-Tk 层冲突时按 species_consensus 仲裁：ANI 层优先于 marker；Shigella/EIEC ↔ E. coli 差异属 expected_divergence（同种），不触发人审。
