# Skills System

Skills are the Hermes Agent's **domain knowledge layer**, orthogonal to Tools (execution capabilities): a Tool answers "what to do",
a Skill answers "when to do it and how to interpret it". Hermes-bacmap registers 4 Skills and uses **three-tier progressive loading** to avoid context bloat.

## The Four Skills

| Skill | Lines | Role | Loading strategy |
|---|---|---|---|
| `bio-router` | 87 | Router: decision tree + tool catalog + pathogen capability matrix | **Always loaded** (system prompt) |
| `run-pipeline` | 95 + 5 refs | Cross-pathogen pipeline operation guide | Loaded on demand when the user requests analysis |
| `interpret-results` | 174 + 2 refs | Result interpretation knowledge base (clinical significance of serotype/MLST/AMR/SNP) | Loaded when the user asks "what does this mean" |
| `bioinfo-analysis` | 91 | General bioinformatics decision tree (non-pipeline analyses) | Loaded for exploratory analyses |

## Three-Tier Progressive Loading

Avoids context explosion from injecting all knowledge at once:

```
Tier 1 · SKILL.md body
  ├─ Always available (bio-router) or loaded on first trigger
  └─ Contains the decision tree, tool catalog, key thresholds

      ↓ when details are needed

Tier 2 · trigger references
  ├─ The Agent proactively loads relevant reference files
  └─ e.g., interpret-results' AMR gene tiering table

      ↓ for pathogen-specific questions

Tier 3 · references/ directory
  ├─ salmonella.md / dec-shigella.md / vpara.md
  ├─ pipeline-params.md / troubleshooting.md
  └─ Loaded only when the corresponding pathogen or scenario appears
```

## bio-router Decision Tree

`bio-router` is the entry skill and is always in the system prompt. It defines the mapping from user intent to tools/skills:

```
User input
│
├── "analyze" + sample name
│   → Call tool: bio_analyze_pathogen
│   → Load skill: hermes_bacmap:run-pipeline
│
├── "annotate" + contigs
│   → Call tool: bio_annotate
│   → Load skill: hermes_bacmap:interpret-results
│
├── "what does X mean"
│   → Load skill: hermes_bacmap:interpret-results
│   → Use the knowledge base to explain serotype / MLST / AMR / SNP
│
├── "compare" + samples
│   → Call tool: bio_snp_tree
│   → Load skill: hermes_bacmap:interpret-results (SNP thresholds)
│
├── "search" + gene / serotype
│   → Call tool: bio_search_samples
│
├── "phylogenetic tree"
│   → Call tool: bio_snp_tree
│
├── "report" + sample name
│   → Call tool: bio_generate_report
│
├── "list samples"
│   → Call tool: bio_list_samples
│
└── Other bioinformatics analyses (non-pipeline)
    → Load skill: hermes_bacmap:bioinfo-analysis
```

bio-router also maintains a **pathogen capability matrix** that tells the Agent which analyses each pathogen supports:

| Pathogen | Species identification | Serotype | MLST | AMR | SNP |
|---|---|---|---|---|---|
| Salmonella | invA | SISTR | gmlst | abricate (CARD/VFDB/PlasmidFinder) | ✅ bwa+bcftools+iqtree |
| E. coli / DEC | uidA | ecoh_serotyper | gmlst | abricate | — |
| Shigella / EIEC | ipaH | shigella_serotyper (58 types) | gmlst | abricate | — |
| V. parahaemolyticus | toxR+tlh | — | — | abricate | — |

## run-pipeline references (Tier 3)

The `run-pipeline` skill ships 5 pathogen-specific reference files, loaded on demand:

| File | Contents |
|---|---|
| `references/salmonella.md` | SISTR, invA, salmonella_2 MLST, SNP reference genome, common AMR genes |
| `references/dec-shigella.md` | ecoh_serotyper, shigella_serotyper (58 types), ipaH, DEC pathotype determination |
| `references/vpara.md` | toxR/tlh species identification, tdh/trh virulence detection, V.para capability status |
| `references/pipeline-params.md` | Snakemake parameters, assembly quality thresholds, per-step runtime/RAM |
| `references/troubleshooting.md` | Common errors + fix steps (lock, OOM, missing DB) |

## interpret-results Knowledge Base

The `interpret-results` skill is the core of clinical interpretation, covering:

| Section | Example content |
|---|---|
| Salmonella serotypes | Kauffmann-White scheme; 6 clinically important serovars; monophasic Typhimurium |
| E. coli / DEC | 5 pathotypes (STEC/EPEC/EIEC/ETEC/EAEC); Big Six non-O157; Shigella vs EIEC |
| MLST clinical significance | ST19=Typhimurium, ST11=Enteritidis, ST131=ExPEC |
| AMR genes | β-lactamase tiering (carbapenemase > ESBL > AmpC > penicillinase); clinical severity grading |
| SNP distance | 0–5 = same transmission chain; 6–15 = possibly related; >50 = different lineages |
| Virulence genes | SPI-1/SPI-2 secretion systems; spv virulence plasmids; sop effector proteins |
| Reporting guidelines | 5 result-summary principles (species confirmation → actionable findings → unusual markers → context → limitations) |

SNP distance thresholds are this skill's most frequent query:

| SNP distance | Interpretation | Public-health action |
|---|---|---|
| 0–5 | Same transmission chain (highly related) | Initiate epidemiological investigation |
| 6–15 | Possible epidemiological link | Judge in combination with epidemiological information |
| 16–50 | Same lineage | Continued surveillance |
| >50 | Different lineages | Rule out direct transmission |

## Registration Mechanism

`src/hermes_bacmap/__init__.py` auto-discovers `skills/*/SKILL.md` and registers it with Hermes:

```python
# 自动发现（简化）
for skill_dir in (Path(__file__).parent.parent.parent / "skills").iterdir():
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        ctx.register_skill(skill_dir.name, skill_md)
```

All 24 tools and 4 skills are registered through this mechanism — no manual declaration needed.

## Manually Loading a Skill

The Agent usually loads them automatically, but you can also trigger loading manually in the conversation:

```
> skill_view("hermes_bacmap:run-pipeline")
> skill_view("hermes_bacmap:interpret-results")
> skill_view("hermes_bacmap:bioinfo-analysis")
```

## Creating a New Skill

1. Create a directory under `skills/`, e.g., `skills/my-analysis/`

2. Write `SKILL.md` (YAML front matter + Markdown body):

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

3. (Optional) Create a `references/` subdirectory for Tier 3 detail documents

4. Restart Hermes; `__init__.py` auto-discovers and registers it

A Skill is pure Markdown with no Python code. It guides the Agent in natural language to call existing Tools and does not add execution capabilities.
If a new execution capability is needed, add a handler in the `tools/` package and register the new tool in `tools/registry.py`.

## Related

- [Hermes Agent interaction](../usage/hermes-agent.md) — real-world usage examples of skills
- [Tool list](../reference/tools.md) — target tools that skills route to
- [Snakemake pipeline](pipeline.en.md) — pipeline details described by the run-pipeline skill
