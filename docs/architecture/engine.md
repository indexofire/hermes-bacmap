# Engine 引擎层

`src/hermes_bacmap/engine/` 是平台的**算法抽象层**，约 800 行，解耦上层管线逻辑与底层具体 CLI 工具（blastn / blastp / minimap2 / bwa）。换比对工具只需改 mode 参数，无需改业务代码。

## 设计目标

| 痛点 | Engine 方案 |
|---|---|
| 不同比对工具输出格式各异（BLAST tabular vs minimap2 PAF） | 统一为 `Hit` dataclass |
| 各 tool handler 重复封装 subprocess | 集中到 backend 类 |
| 业务代码硬编码 `blastn` / `bwa` 命令 | 通过 `mode="auto"` 自动选型 |
| 新增比对工具要改多处 | 注册到 `Registry` 即可用 |

## 目录结构

```
engine/
├── __init__.py          87 行   SequenceMatcher facade + 自动后端选择
├── hits.py             115 行   Hit dataclass（统一 BLAST tabular + PAF 解析）
├── read_mapper.py      136 行   ReadMapper facade（BWA-MEM + Minimap2）
├── registry.py          28 行   Registry（name → callable，小写键，懒加载）
├── _env.py                     pixi 环境定位 + which() 工具查找
├── utils.py                    classify_allele / confidence_tier / merge_intervals
└── backends/
    ├── __init__.py      44 行   后端注册表 + 懒加载
    └── blast.py                BlastBackend + MinimapBackend 实现
```

## 核心组件

### Hit — 统一比对结果

`hits.py` 定义 `Hit` dataclass，屏蔽 BLAST tabular 与 minimap2 PAF 的格式差异：

```python
@dataclass
class Hit:
    query_id: str = ""
    subject_id: str = ""
    identity: float = 0.0          # 百分比
    query_coverage: float = 0.0
    subject_coverage: float = 0.0
    evalue: float = 0.0
    bit_score: float = 0.0
    query_start: int = 0
    query_end: int = 0
    subject_start: int = 0
    subject_end: int = 0
    strand: str = "+"
    alignment_length: int = 0
    mismatches: int = 0
    mapq: int = 0                  # minimap2 专属
    backend: str = ""              # "blast" / "minimap2"
```

两个工厂方法负责解析：

| 方法 | 输入 | 字段计算 |
|---|---|---|
| `Hit.from_blast_line(line)` | BLAST `outfmt 6`（14 列） | `query_coverage = aln_len / qlen`，strand 由 sstart vs send 推断 |
| `Hit.from_paf_line(line)` | minimap2 PAF（≥12 列 + NM tag） | `identity = nmatch / aln_len`，mismatches 从 `NM:i:` tag 解析 |

### SequenceMatcher — 序列匹配 facade

入口类，自动选择后端：

```python
from hermes_bacmap.engine import SequenceMatcher

hits = SequenceMatcher.match(
    query="contigs.fasta",
    db_prefix="data/reference/card",
    mode="auto",           # 自动选型
    min_identity=80.0,
    min_coverage=80.0,
)
```

**自动后端选择策略**（`_select_backend`）：

| 条件 | 选中后端 | 理由 |
|---|---|---|
| `query_type="prot"` | `blastp` | 蛋白查询必须 blastp |
| 查询文件 > 10 MB | `minimap2` | 大文件 blastn 太慢 |
| 其他 | `blastn` | 默认核酸比对 |

也可显式指定：`mode="blastn"` / `"blastp"` / `"blastx"` / `"tblastn"` / `"minimap2"`。

### ReadMapper — 读段比对 facade

将测序 reads 比对到参考基因组，产出排序并索引的 BAM：

```python
from hermes_bacmap.engine import ReadMapper

result = ReadMapper.map(
    reads=["sample_R1.fq.gz", "sample_R2.fq.gz"],
    reference="data/reference/salmonella_LT2_ref.fasta",
    out_bam="results/sample/snp/snps.bam",
    mode="auto",
)
```

| mode | 实现类 | 触发条件 |
|---|---|---|
| `bwa` | `BwaReadMapper` | reads 是 FASTQ（默认） |
| `minimap2` | `Minimap2ReadMapper` | reads 是 FASTA（长读） |

两个 mapper 都自动：BWA 索引缺失则建索引、samtools sort、samtools index。

### Registry — 后端注册表

`registry.py` 提供通用 name → callable 注册，键统一小写，支持懒加载：

```python
class Registry:
    def register(self, name: str, func: Callable) -> None: ...
    def get(self, name: str) -> Callable: ...      # 未注册 raise KeyError
    def available(self) -> dict[str, Callable]: ...
    def has(self, name: str) -> bool: ...
```

`backends/__init__.py` 用它注册内置后端：

```python
_BUILTINS = {
    "blastn":   ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "blastp":   ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "blastx":   ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "tblastn":  ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "minimap2": ("hermes_bacmap.engine.backends.blast", "MinimapBackend"),
}
```

`get_backend(name)` 懒加载：首次请求某后端时才 import 对应模块，避免启动时全量加载。

## 后端分发

```
SequenceMatcher.match(mode)
  │
  ├── mode == "auto"
  │     └── _select_backend(query, query_type)
  │           ├── query_type="prot"     → blastp
  │           ├── 文件 > 10MB           → minimap2
  │           └── 其他                  → blastn
  │
  ├── mode in {blastp, blastx, tblastn}
  │     └── get_backend(mode, tool=mode)   # 传 tool 区分蛋白搜索
  │
  └── mode == "minimap2"
        └── backend.find(query, target, ...)  # 用 db_path 而非 db_prefix
```

ReadMapper 同理：FASTA reads → minimap2，FASTQ reads → bwa。

## gene_scanner 如何委托

`gene_scanner.py`（420 行）是通用基因扫描引擎，支持 9 种数据库（card / vfdb / ecoh / plasmidfinder / resfinder / ncbi / megares / victors / ecoli_vf）。它**不直接调 blastn**，而是委托给 `engine.SequenceMatcher`：

```python
# gene_scanner.py 核心逻辑（简化）
from hermes_bacmap.engine import SequenceMatcher

def scan(contigs: str, database: str, min_identity=80, min_coverage=80) -> list[dict]:
    db_prefix = f"data/reference/{database}"
    hits = SequenceMatcher.match(
        query=contigs,
        db_prefix=db_prefix,
        mode="auto",
        min_identity=min_identity,
        min_coverage=min_coverage,
    )
    # 检查返回码，非零 raise（防止静默假阴性）
    return [h.to_dict() for h in hits if h.identity >= min_identity]
```

同样，`ecoh_serotyper.py`、`species_identifier.py`、`shigella_serotyper.py` 都通过 `SequenceMatcher` 调底层 BLAST，零代码重复。

## 扩展新后端

新增比对工具（如 Diamond）只需两步：

```python
# 1. 实现 backend 类
class DiamondBackend:
    def find(self, query, db_path, min_identity=0, min_coverage=0, **kw):
        # 调 diamond blastp，解析输出为 Hit 列表
        return [Hit.from_blast_line(line) for line in stdout.splitlines()]

# 2. 注册
from hermes_bacmap.engine.backends import register
register("diamond", DiamondBackend)
```

之后 `SequenceMatcher.match(query, db_prefix, mode="diamond")` 即可用。

## 相关

- [GOM 数据模型](gom.md) — Hit 结果最终序列化进 `payload_json`
- [Snakemake 管线](pipeline.md) — 管线规则通过 `bio_gene_scan` Hermes tool 间接使用 engine
- [工具列表](../reference/tools.md) — 18 个 tool 中 `bio_blast` / `bio_align` / `bio_gene_scan` 均基于 engine
