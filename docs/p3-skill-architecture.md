# P3: Skill 组织架构方案（待决策）

> **状态**: 待确认方向后再实施
> **创建时间**: 2026-07-03
> **前置条件**: seqops.py 算法抽象层完成后，管线结构稳定再重组 skills

---

## 背景

当前 4 个 skills 按病原命名（`analyze-salmonella`），但管线代码已经是跨病原的：
- 一个 Snakemake pipeline，自动物种路由（invA/uidA/ipaH/toxR）
- species_identifier 自动分派到 Salmonella/DEC/Shigella/V.para
- collect_summary.py 自动分流血清型（SISTR/ecoh_serotyper/shigella_serotyper）

`analyze-salmonella` skill 中 **86% 的内容不是 Salmonella 特有的**。

---

## 三个方案

### 方案 A：按病原扩展（当前模式）

```
skills/
├── bio-router/
├── analyze-salmonella/      ← 当前
├── analyze-dec-shigella/    ← 新增
├── analyze-vpara/           ← 新增
├── interpret-results/
└── bioinfo-analysis/
```

- 直观，每个病原一个 skill
- 但 90% 管线逻辑重复（QC/assembly/MLST/AMR/report 完全一样）
- 新增病原 = 新增 skill = 维护成本线性增长

### 方案 B：按分析任务拆分

```
skills/
├── bio-router/
├── run-pipeline/            ← 通用管线操作
├── interpret-serotype/      ← 血清型解读（跨病原）
├── interpret-amr/           ← AMR 解读
├── interpret-snp/           ← SNP/系统发育解读
├── interpret-annotation/    ← 注释解读
└── bioinfo-analysis/
```

- 每个技能聚焦单一任务，可复用
- 但 skill 数量膨胀到 7+
- 用户经常需要同时加载多个（serotype + AMR + SNP）

### 方案 C：重命名 + 引用分离（推荐）

```
skills/
├── bio-router/              ← 始终加载，路由到其他 skills
├── run-pipeline/            ← analyze-salmonella 改名
│   ├── SKILL.md             ← 主体通用管线操作（所有病原）
│   └── references/
│       ├── salmonella.md    ← Salmonella 特有（SISTR, invA, salmonella_2 MLST）
│       ├── dec-shigella.md  ← DEC/Shigella 特有（ecoh, shigella_serotyper, ipaH, pathotype）
│       └── vpara.md         ← V. para 特有（toxR, tlh, tdh, trh）
├── interpret-results/       ← 保持不变（已跨病原）
│   ├── SKILL.md
│   └── references/
│       ├── amr-gene-reference.md       ← 已存在
│       └── snp-distance-thresholds.md  ← 已存在
└── bioinfo-analysis/        ← 保持不变
```

- skill 总数保持 4 个
- 新增病原 = 加一个 reference 文件（references/vpara.md），不加新 skill
- 主体通用，细节分层（Anthropic 3-tier progressive disclosure）
- 与管线代码架构一致（一个 pipeline + 自动物种路由）

---

## 方案 C 的具体改动

### 1. analyze-salmonella → run-pipeline

| 当前 | 改后 |
|---|---|
| `name: analyze-salmonella` | `name: run-pipeline` |
| `description: "Salmonella WGS..."` | `description: "Pathogen WGS pipeline..."` |
| 主体含 Salmonella 特有步骤 | 主体通用，Salmonella 细节移到 references/ |

### 2. 新增 references 文件

- `references/salmonella.md` — SISTR 血清型、invA 物种验证、salmonella_2 MLST scheme、SPN 参考基因组
- `references/dec-shigella.md` — ecoh_serotyper O:H 分型、shigella_serotyper 58 型、ipaH 验证、DEC pathotype 判定
- `references/vpara.md` — toxR/tlh 物种鉴定、tdh/trh 毒力检测（未来 VPsero O/K 血清型）

### 3. bio-router 更新

决策树从 "分析 SAM-XXX → load analyze-salmonella" 改为 "分析 → load run-pipeline"。

### 4. Tool 重命名（可选，待定）

`bio_analyze_salmonella` → `bio_analyze_pathogen`？
- Pro: 名称与实际功能匹配（管线支持 4 种病原）
- Con: 已注册的 tool name 变更，需要同步 schemas.py + __init__.py + tools.py
- 风险: 低（LLM 每次会话重新读 schema，无持久记忆）

---

## 决策时机

**建议在 seqops.py 算法抽象层完成后**再执行 P3 重组：

1. seqops.py 会改变管线的内部结构（Snakemake rules 可能调整）
2. 管线结构稳定后，skill 内容才能准确描述操作流程
3. 避免重组 skill 后又因管线变更需要返工

---

## 与 seqops.py 的关系

seqops.py 抽象层完成后：

```
当前 Snakemake shell:
  bwa mem ... | samtools sort ... | bcftools mpileup ... | bcftools call ...

未来 Python 调用:
  reads = seqops.ReadMapper.map(fastq, reference, mode="auto")
  variants = seqops.VariantCaller.call(reads, reference, mode="auto")
```

这将使得 skill 内容更加简洁——不再需要描述具体 CLI 工具的参数，只需描述分析步骤的逻辑。
