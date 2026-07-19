# Skills 技能系统

Skills 是 Hermes Agent 的**领域知识层**，与 Tools（执行能力）正交：Tool 是"做什么"，Skill 是"何时做、怎么解读"。Hermes-bacmap 注册了 4 个 Skills，采用**三层渐进式加载**避免上下文膨胀。

## 四个 Skills

| Skill | 行数 | 角色 | 加载策略 |
|---|---|---|---|
| `bio-router` | 87 | 路由器：决策树 + 工具目录 + 病原能力矩阵 | **始终加载**（system prompt） |
| `run-pipeline` | 95 + 5 refs | 跨病原管线操作指南 | 用户请求分析时按需加载 |
| `interpret-results` | 174 + 2 refs | 结果解读知识库（血清型/MLST/AMR/SNP 临床意义） | 用户问"这是什么意思"时加载 |
| `bioinfo-analysis` | 91 | 通用生信决策树（非管线类分析） | 探索性分析时加载 |

## 三层渐进式加载

避免一次性灌入全部知识导致 context 爆炸：

```
Tier 1 · SKILL.md 主体
  ├─ 始终可用（bio-router）或首次触发时加载
  └─ 包含决策树、工具目录、关键阈值

      ↓ 需要细节时

Tier 2 · 触发引用
  ├─ Agent 主动加载相关 reference 文件
  └─ 如 interpret-results 的 AMR 基因分级表

      ↓ 病原特异性问题时

Tier 3 · references/ 目录
  ├─ salmonella.md / dec-shigella.md / vpara.md
  ├─ pipeline-params.md / troubleshooting.md
  └─ 仅在对应病原或场景出现时加载
```

## bio-router 决策树

`bio-router` 是入口 skill，始终在 system prompt 中。它定义了用户意图到工具/skill 的映射：

```
用户输入
│
├── "分析 / analyze" + 样本名
│   → Call tool: bio_analyze_pathogen
│   → Load skill: hermes_bacmap:run-pipeline
│
├── "注释 / annotate" + contigs
│   → Call tool: bio_annotate
│   → Load skill: hermes_bacmap:interpret-results
│
├── "X 是什么意思 / what does X mean"
│   → Load skill: hermes_bacmap:interpret-results
│   → 用知识库解释 serotype / MLST / AMR / SNP
│
├── "比较 / compare" + 样本
│   → Call tool: bio_snp_tree
│   → Load skill: hermes_bacmap:interpret-results（SNP 阈值）
│
├── "搜索 / search / 找" + 基因 / 血清型
│   → Call tool: bio_search_samples
│
├── "系统发育树 / phylogenetic tree"
│   → Call tool: bio_snp_tree
│
├── "报告 / report" + 样本名
│   → Call tool: bio_generate_report
│
├── "列出样本 / list samples"
│   → Call tool: bio_list_samples
│
└── 其他生信分析（非管线）
    → Load skill: hermes_bacmap:bioinfo-analysis
```

bio-router 同时维护**病原能力矩阵**，告诉 Agent 每种病原支持哪些分析：

| 病原 | 物种鉴定 | 血清型 | MLST | AMR | SNP |
|---|---|---|---|---|---|
| Salmonella | invA | SISTR | gmlst | abricate（CARD/VFDB/PlasmidFinder） | ✅ bwa+bcftools+iqtree |
| E. coli / DEC | uidA | ecoh_serotyper | gmlst | abricate | — |
| Shigella / EIEC | ipaH | shigella_serotyper（58 型） | gmlst | abricate | — |
| V. parahaemolyticus | toxR+tlh | — | — | abricate | — |

## run-pipeline references（Tier 3）

`run-pipeline` skill 自带 5 个病原特异性参考文件，按需加载：

| 文件 | 内容 |
|---|---|
| `references/salmonella.md` | SISTR、invA、salmonella_2 MLST、SNP 参考基因组、常见 AMR 基因 |
| `references/dec-shigella.md` | ecoh_serotyper、shigella_serotyper（58 型）、ipaH、DEC pathotype 判定 |
| `references/vpara.md` | toxR/tlh 物种鉴定、tdh/trh 毒力检测、V.para 能力状态 |
| `references/pipeline-params.md` | Snakemake 参数、组装质量阈值、各步耗时/RAM |
| `references/troubleshooting.md` | 常见错误 + 修复步骤（lock、OOM、缺失 DB） |

## interpret-results 知识库

`interpret-results` skill 是临床解读的核心，覆盖：

| 章节 | 内容示例 |
|---|---|
| Salmonella 血清型 | Kauffmann-White 方案；6 种临床重要血清型；monophasic Typhimurium |
| E. coli / DEC | 5 种 pathotype（STEC/EPEC/EIEC/ETEC/EAEC）；Big Six non-O157；Shigella vs EIEC |
| MLST 临床意义 | ST19=Typhimurium、ST11=Enteritidis、ST131=ExPEC |
| AMR 基因 | β-内酰胺酶分级（carbapenemase > ESBL > AmpC > penicillinase）；临床严重性分级 |
| SNP 距离 | 0–5 = 同源传播链；6–15 = 可能相关；>50 = 不同谱系 |
| 毒力基因 | SPI-1/SPI-2 分泌系统；spv 毒力质粒；sop 效应蛋白 |
| 报告指南 | 5 条结果摘要原则（物种确认 → 可执行发现 → 非常规标记 → 上下文 → 局限性） |

SNP 距离阈值是该 skill 最常用的查询：

| SNP 距离 | 解读 | 公卫行动 |
|---|---|---|
| 0–5 | 同源传播链（高度相关） | 启动流行病学调查 |
| 6–15 | 可能有流行病学关联 | 结合流行病学信息判断 |
| 16–50 | 同一谱系 | 持续监测 |
| >50 | 不同谱系 | 排除直接传播 |

## 注册机制

`src/hermes_bacmap/__init__.py` 自动发现 `skills/*/SKILL.md` 并注册到 Hermes：

```python
# 自动发现（简化）
for skill_dir in (Path(__file__).parent.parent.parent / "skills").iterdir():
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        ctx.register_skill(skill_dir.name, skill_md)
```

24 个 tools 与 4 个 skills 全部通过此机制注册，无需手动声明。

## 手动加载 Skill

Agent 通常自动加载，也可在对话中手动触发：

```
> skill_view("hermes_bacmap:run-pipeline")
> skill_view("hermes_bacmap:interpret-results")
> skill_view("hermes_bacmap:bioinfo-analysis")
```

## 创建新 Skill

1. 在 `skills/` 下建目录，如 `skills/my-analysis/`

2. 编写 `SKILL.md`（YAML front matter + Markdown 主体）：

   ```markdown
   ---
   name: my-analysis
   description: >
     一句话描述触发条件与用途。Load when user mentions ...
   version: 0.1.0
   metadata:
     hermes:
       category: bioinfo
       tags: [mycology, resistance]
   ---

   # My Analysis

   ## When to Use
   - ...

   ## Procedure
   1. ...
   ```

3. （可选）建 `references/` 子目录放 Tier 3 细节文档

4. 重启 Hermes，`__init__.py` 自动发现并注册

Skill 是纯 Markdown，无 Python 代码。它通过自然语言指导 Agent 调用已有 Tools，不新增执行能力。若需要新的执行能力，应在 `tools/` 包新增 handler 并在 `tools/registry.py` 注册新 tool。

## 相关

- [Hermes Agent 交互](../usage/hermes-agent.md) — skill 的实际使用示例
- [工具列表](../reference/tools.md) — skill 路由的目标工具
- [Snakemake 管线](pipeline.md) — run-pipeline skill 描述的管线细节
