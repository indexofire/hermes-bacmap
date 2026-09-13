# 案例：tlh 交叉反应——marker 误判 V. alginolyticus 为 V. parahaemolyticus

验证轮次：物种鉴定验证第一轮（2026-09）· 数据集：NCBI Pathogen 追踪病原 RefSeq 参考基因组 17 株
（`tests/fixtures/validation_genomes/manifest.tsv` 真值表）

## 现象

| 方法 | GCF_023650915.1（NCBI 标注 *Vibrio alginolyticus* E110）判定 |
|---|---|
| marker 靶基因 | ❌ V_parahaemolyticus（cross-reaction） |
| mash_refseq（159MB 库） | ✅ 正确排除 V.para（最近邻全为 alginolyticus 复合群） |

## 取证（三路独立证据）

1. **真值可信**：skani 直接比对 E110 vs V.para RIMD 2210633 参考株 → **ANI 87.56%、覆盖 35.5%**
   （物种边界 95%，远在界外——E110 不可能是 V.para）；mash 全库最近邻前 4 全为 V. alginolyticus
   复合群（diabolicus/chemaguriensis/antiquarius，sim≈0.94），V.para 排第 5（sim 0.895）。
2. **机制**：命中的是 **tlh**（identity **85.2%**、coverage 86%），仅高出 85% 阈值 0.2 个百分点。
   V. alginolyticus 携带 tlh 同源基因（tlh 并非绝对种特异）；toxR 未命中（<85%）。
3. **方法学结论**：marker 层交叉反应真实存在；mash ANI 层 100% 正确区分——分层仲裁设计的前提成立。

## 落地的改进

| 改进 | 实现 | 验证 |
|---|---|---|
| 置信度分级 | 最佳命中 ≥90% → high；85-90% → medium + notes 建议 ANI 复核 | `TestConfidenceTiers` |
| tlh 近缘守卫 | tlh 单基因 <90% 命中 → 物种判定抑制为 Unknown（notes 携带复核建议） | `TestNearRelativeGuard`（本案例回归测试） |
| 知识库 | `skills/interpret-results/references/species-marker-crossreactions.md`（AI 层判读规则与话术） | — |

改进后该株 marker 结果：species=Unknown / confidence=low / notes 携带 ANI 复核建议——
验证 harness 从 94% 升至 **17/17 (100%)**。

## 启示

- "物种特异 marker" 的特异性是相对的——**近缘种同源基因可在 85% 边缘区滑过宽松阈值**；
  凡引入新病原，其 marker 必须用近缘种做阴性对照实验（P1 计划已含此项）。
- 全基因组方法（ANI/MinHash）与 marker 是互补证据层，不是替代关系。
- 真实数据验证不可省略：本 bug（及 mash distance 列序 bug）均无法被纯单测发现。
