# bacmap → hermes-bacmap 移植计划书

> **创建时间**: 2026-07-03
> **状态**: 分析完成，待实施
> **源码位置**: `~/repo/bacmap` (4013 行 Python)
> **目标位置**: `~/repo/github/hermes-bacmap/src/hermes_bacmap/`

---

## 一、bacmap 架构概要

### 三层架构

```
Pipeline (pipeline.py)        ← JSON plan 驱动，动态加载模块
   ↓
Module  (module/)             ← 分析模块：MLST/Serotype/Virulence/GeneAbsence
   ↓
Engine  (engine/)             ← 工具封装：BlastEngine/BlastAligner/MinimapAligner
```

### 核心设计模式

| 模式 | 位置 | hermes-bacmap 有？ |
|---|---|---|
| **Plugin Registry** (懒加载) | `util/registry.py` + `finder/` + `classifier/` + `serotyping/` | ❌ 无 |
| **Template Method** | `GeneFinderModule.run() → interpret()` | ❌ 无 |
| **Strategy** | finder registry (blast/minimap2), serotype strategy registry | ❌ 无 |
| **Config-driven orchestration** | `plan/*.json` 定义物种分析流程 | ❌ 用 Snakemake 代替 |
| **统一 finder 契约** | `find_hits(genome, config, engine_manager) → list[dict]` | ❌ gene_scanner 绑死 blastn |

### 两代 Engine — 只保留新一代

| 代次 | 文件 | 决策 |
|---|---|---|
| 旧 (EngineManager) | `engine/blast.py`, `engine/base.py`, `engine/manager.py` | **丢弃**（过于贫血/硬编码） |
| 新 (Aligner) | `engine/align.py` | **保留移植**（BlastAligner + MinimapAligner） |

新一代更成熟：支持多后端（blastn/blastp/blastx/diamond + minimap2）、返回强类型 `BlastHit`/`MinimapHit`、参数别名映射。**seqops 只基于 align.py 构建。**

---

## 二、代码可移植性评估

### Tier 1 — 直接移植（高价值，低风险）

| 源文件 | 行数 | 移植目标 | 价值 |
|---|---|---|---|
| `util/registry.py` | 24 | `seqops/registry.py` | 插件注册基础设施，3 个系统共用 |
| `finder/registry.py` | 44 | `seqops/backend_registry.py` | 后端发现 + 懒加载模板 |
| `engine/align.py: BlastHit` | 57 | `seqops/hits.py: Hit` | 标准化比对结果 dataclass |
| `engine/align.py: MinimapHit` | 142 | `seqops/hits.py: Hit` | PAF 解析器（含 NM/AS/MD/cg 标签） |
| `engine/align.py: BlastAligner` | 187 | `seqops/backends/blast.py` | blastn/blastp/diamond 多模式 + 参数别名 |
| `engine/align.py: MinimapAligner` | 73 | `seqops/backends/minimap2.py` | minimap2 PAF 对齐 |
| `module/serotyping._merge_subject_coverage` | 29 | `seqops/utils.py: merge_intervals` | HSP 区间合并（代码库中重复 4 次，统一） |

### Tier 2 — 改编移植（需适配 hermes 架构）

| 源文件 | 行数 | 移植目标 | 改动 |
|---|---|---|---|
| `engine/serotype._confidence` | 11 | `seqops/utils.py: confidence_tier` | 通用 5 级质量评分（不限于 Kaptive） |
| `engine/mlst._classify_allele` | 19 | `seqops/utils.py: classify_allele` | 4 级等位基因分类（exact/novel/partial/missing） |
| `engine/mlst._ensure_db` | 10 | `seqops/backends/blast.py: ensure_index` | 自动建索引（缺 .nhr 时自动 makeblastdb） |
| `module/genotyping: gene_synonyms` | 34 | `gene_scanner.py` | 基因名别名归一化（{canonical: [aliases]} 和 {alias: canonical} 双格式） |
| `pipeline._resolve_config_paths` | 12 | `seqops/config.py` | 递归路径解析（`*_path`/`*_file` 后缀自动补全为绝对路径） |

### Tier 3 — 借鉴思想（不直接移植代码）

| 源概念 | 借鉴方式 |
|---|---|
| JSON plan 驱动 | 考虑作为 Skill 增强：让 LLM 生成 plan JSON，而非替代 Snakemake |
| `GeneFinderModule` template method | 如果 hermes 加 Module 层，采用 run() → interpret() 模式 |
| `classifier/` 注册表 | hermes 的 `deterministic_verifier.py` 已有类似功能，但无插件化 |

### Tier 4 — 不移植

| 源文件 | 原因 |
|---|---|
| `engine/blast.py` (BlastEngine) | 旧一代，被 `engine/align.py: BlastAligner` 取代 |
| `engine/base.py` (BaseEngine ABC) | 过于贫血（只有 check_dependencies） |
| `engine/manager.py` (EngineManager) | 硬编码引擎表，用 Registry 代替 |
| `analyzers/` (整个目录) | 死代码（导入不存在的 `bacmap.modules.*`） |
| `engine/_mlst.py`, `engine/_serotype.py` | 完全重复（diff 确认） |
| `module/serotyping_old.py` | 已被 serotyping.py 取代 |
| `module/serotyping: vpa_kaptive_like_strategy` | **自行开发 V. para 血清型工具，不采用 Kaptive 方案** |
| `engine/mlst.py` (standalone) | 被 `module/mlst.py` 取代；hermes 用 gmlst |
| `engine/serotype.py` (standalone) | 被 `module/serotyping.py` 取代 |
| `reporting/renderer.py` | hermes 有 `generate_report.py` (HTML) |
| `io/fasta.py` | 15 行 trivial biopython 封装 |
| `config.py` | Conda-prefix 逻辑不适用 hermes (pixi/uv) |
| `db/` | 无 Python 源码（只有孤儿 .pyc） |

---

## 三、移植后的 seqops.py 架构

```
src/hermes_bacmap/seqops/
├── __init__.py              ← 公共 API：SequenceMatcher, ReadMapper, Hit
├── registry.py              ← 移植自 bacmap util/registry.py（24 行）
├── hits.py                  ← 统一 Hit dataclass（合并 BlastHit + MinimapHit）
├── utils.py                 ← merge_intervals, confidence_tier, classify_allele
├── config.py                ← resolve_paths（移植 _resolve_config_paths）
└── backends/
    ├── __init__.py          ← 后端注册表（移植 finder/registry.py 模式）
    ├── blast.py             ← BlastBackend（移植 BlastAligner + BlastEngine 精华）
    ├── minimap2.py          ← MinimapBackend（移植 MinimapAligner）
    └── (未来: bwa.py, kmer.py)
```

### 核心接口设计

```python
# seqops/__init__.py

from .hits import Hit
from .backends import get_backend

class SequenceMatcher:
    """统一序列匹配 — 自动选择 BLAST / minimap2 / k-mer"""

    @classmethod
    def match(cls, query, db_name, mode="auto", query_type="auto",
              min_identity=80.0, min_coverage=80.0, **kwargs):
        if mode == "auto":
            mode = cls._select_backend(query, query_type)
        backend = get_backend(mode)
        hits = backend.find(query, db_name, min_identity, min_coverage, **kwargs)
        return hits

    @staticmethod
    def _select_backend(query, query_type):
        if query_type == "prot":
            return "blast"
        query_size = Path(query).stat().st_size
        if query_size > 10_000_000:
            return "minimap2"
        return "blast"


class ReadMapper:
    """统一读段比对 — 自动选择 bwa / minimap2"""

    @classmethod
    def map(cls, reads, reference, mode="auto", out_bam=None, **kwargs):
        if mode == "auto":
            mode = "bwa"  # 默认短读段
        backend = get_backend(mode)
        return backend.map(reads, reference, out_bam, **kwargs)
```

### 统一 Hit 数据类

```python
# seqops/hits.py

@dataclass
class Hit:
    """统一比对结果（合并 BLAST tabular + minimap2 PAF）"""
    query_id: str
    subject_id: str
    identity: float
    coverage: float
    evalue: float = 0.0
    bit_score: float = 0.0
    query_start: int = 0
    query_end: int = 0
    subject_start: int = 0
    subject_end: int = 0
    strand: str = "+"
    alignment_length: int = 0
    backend: str = ""       # "blast" | "minimap2" | "bwa"

    @classmethod
    def from_blast_line(cls, line, outfmt): ...  # 移植自 BlastHit

    @classmethod
    def from_paf_line(cls, line): ...             # 移植自 MinimapHit
```

---

## 四、对现有 hermes-bacmap 代码的影响

### gene_scanner.py 改动

```python
# 当前（硬编码 blastn）
from .gene_scanner import scan

# 改后（通过 seqops）
from .seqops import SequenceMatcher
hits = SequenceMatcher.match(contigs, "card", mode="auto")
```

gene_scanner 的 `scan()` 函数变为 seqops.SequenceMatcher 的薄包装。

### genome_annotator.py 改动

```python
# 当前（直接调 blastp）
proc = subprocess.run(["blastp", ...])

# 改后（通过 seqops）
hits = SequenceMatcher.match(proteins_faa, "prokka_sprot",
                              mode="blast", query_type="prot")
```

### tools.py bio_align 改动

```python
# 当前（bwa/minimap2 分派硬编码）
if aligner == "bwa-mem": ...
elif aligner == "minimap2": ...

# 改后
from .seqops import ReadMapper
bam_path = ReadMapper.map(reads, reference, mode="auto")
```

### 新增：vpa_serotyper.py

**自行开发**（不采用 Kaptive 方案）。bacmap 的 `vpa_kaptive_like_strategy` 仅作参考，
了解 O/K 基因簇比对的思路（区间合并、基因完整性检查），但实现完全独立。

---

## 五、移植优先级和顺序

```
阶段 1（seqops 核心，~300 行）
  ├── 移植 registry.py (24 行)
  ├── 合并 Hit dataclass (~80 行)
  ├── 实现 BlastBackend (~120 行)
  └── 实现 utils.merge_intervals (~30 行)

阶段 2（集成，改动现有代码）
  ├── gene_scanner.py → 委托 seqops
  ├── genome_annotator.py → 委托 seqops
  └── 验证：所有现有测试通过

阶段 3（扩展后端）
  ├── MinimapBackend (~80 行)
  ├── BwaBackend (~80 行)
  └── tools.py bio_align → 委托 seqops.ReadMapper

阶段 4（新增功能）
  ├── gene_synonyms 归一化（移植到 gene_scanner）
  ├── classify_allele / confidence_tier（用于 MLST 和血清型质量评分）
  └── vpa_serotyper.py（自行开发，不采用 Kaptive）
```

---

## 六、风险和注意事项

| 风险 | 缓解 |
|---|---|
| 移植后现有 96 测试可能失败 | 阶段 2 逐模块迁移，每步跑测试 |
| bacmap 的 finder 契约返回 dict，hermes 返回 dataclass | 统一用 Hit dataclass，保留 to_dict() |
| bacmap 的 engine_manager 依赖注入 vs hermes 的模块级函数 | seqops 用类方法 + 注册表，不需要 engine_manager |
| bacmap 的 plan JSON 与 Snakemake 冲突 | 不移植 plan 系统，只移植 engine/finder 层 |
| `_merge_coverage` 在 bacmap 中重复 4 次 | 移植时统一为 seqops.utils.merge_intervals 一份 |

---

## 七、代码量估算

| 组件 | 新增行数 | 改动行数 | 来源 |
|---|---|---|---|
| seqops/ 新目录 | ~400 | 0 | 移植 + 新写 |
| gene_scanner.py | 0 | ~50（委托 seqops） | 改编 |
| genome_annotator.py | 0 | ~30（委托 seqops） | 改编 |
| tools.py | 0 | ~40（bio_align 委托） | 改编 |
| vpa_serotyper.py | ~200 | 0 | 自行开发（不移植 bacmap） |
| **合计** | **~600** | **~120** | |
