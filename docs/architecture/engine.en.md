# Engine Layer

`src/hermes_bacmap/engine/` is the platform's **algorithm abstraction layer**, about 1000 lines, decoupling upper-layer pipeline logic from
the underlying concrete CLI tools (blastn / blastp / minimap2 / bwa / mash / sourmash). Switching the alignment tool only requires changing
the mode parameter — no business-code changes needed.

## Design Goals

| Pain point | Engine solution |
|---|---|
| Different alignment tools output different formats (BLAST tabular vs minimap2 PAF) | Unified into the `Hit` dataclass |
| Tool handlers repeatedly wrap subprocess | Centralized in backend classes |
| Business code hardcodes `blastn` / `bwa` commands | Automatic selection via `mode="auto"` |
| Adding a new alignment tool requires changes in many places | Register in `Registry` and it is ready to use |

## Directory Structure

```
engine/
├── __init__.py           87 lines  SequenceMatcher facade + automatic backend selection
├── hits.py              115 lines  Hit dataclass (unified BLAST tabular + PAF parsing)
├── read_mapper.py       136 lines  ReadMapper facade (BWA-MEM + Minimap2)
├── registry.py           28 lines  Registry (name → callable, lowercase keys, lazy loading)
├── _env.py                         pixi environment location + which() tool lookup
├── utils.py                        classify_allele / confidence_tier / merge_intervals
├── utils.py (project)    67 lines  parse_mlst / parse_abricate_tsv / read_json_file (shared parsing)
└── backends/
    ├── __init__.py       44 lines  Backend registry + lazy loading (7 backends)
    ├── blast.py                    BlastBackend (blastn/blastp/blastx/tblastn)
    ├── minimap2.py                 MinimapBackend (PAF alignment + .mmi index)
    └── kmer.py                     MashBackend + SourmashBackend (MinHash genome distance)
```

## Core Components

### Hit — unified alignment result

`hits.py` defines the `Hit` dataclass, shielding callers from format differences between BLAST tabular and minimap2 PAF:

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

Two factory methods handle parsing:

| Method | Input | Field computation |
|---|---|---|
| `Hit.from_blast_line(line)` | BLAST `outfmt 6` (14 columns) | `query_coverage = aln_len / qlen`; strand inferred from sstart vs send |
| `Hit.from_paf_line(line)` | minimap2 PAF (≥12 columns + NM tag) | `identity = nmatch / aln_len`; mismatches parsed from the `NM:i:` tag |

### SequenceMatcher — sequence matching facade

The entry class, which selects the backend automatically:

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

**Automatic backend selection strategy** (`_select_backend`):

| Condition | Selected backend | Rationale |
|---|---|---|
| `query_type="prot"` | `blastp` | Protein queries require blastp |
| Query file > 10 MB | `minimap2` | blastn is too slow for large files |
| Otherwise | `blastn` | Default nucleotide alignment |

You can also specify explicitly: `mode="blastn"` / `"blastp"` / `"blastx"` / `"tblastn"` / `"minimap2"`.

### ReadMapper — read mapping facade

Maps sequencing reads to a reference genome, producing a sorted and indexed BAM:

```python
from hermes_bacmap.engine import ReadMapper

result = ReadMapper.map(
    reads=["sample_R1.fq.gz", "sample_R2.fq.gz"],
    reference="data/reference/genomes/salmonella_LT2.fasta",
    out_bam="results/sample/snp/snps.bam",
    mode="auto",
)
```

| mode | Implementation class | Trigger condition |
|---|---|---|
| `bwa` | `BwaReadMapper` | reads are FASTQ (default) |
| `minimap2` | `Minimap2ReadMapper` | reads are FASTA (long reads) |

Both mappers automatically: build the BWA index if missing, run samtools sort and samtools index.

### Registry — backend registry

`registry.py` provides a generic name → callable registry with uniformly lowercase keys and lazy loading:

```python
class Registry:
    def register(self, name: str, func: Callable) -> None: ...
    def get(self, name: str) -> Callable: ...      # 未注册 raise KeyError
    def available(self) -> dict[str, Callable]: ...
    def has(self, name: str) -> bool: ...
```

`backends/__init__.py` uses it to register the built-in backends:

```python
_BUILTINS = {
    "blastn":   ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "blastp":   ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "blastx":   ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "tblastn":  ("hermes_bacmap.engine.backends.blast", "BlastBackend"),
    "minimap2": ("hermes_bacmap.engine.backends.blast", "MinimapBackend"),
}
```

`get_backend(name)` lazy-loads: the corresponding module is imported only when a backend is first requested, avoiding a full load at startup.

## Backend Dispatch

```
SequenceMatcher.match(mode)
  │
  ├── mode == "auto"
  │     └── _select_backend(query, query_type)
  │           ├── query_type="prot"     → blastp
  │           ├── file > 10MB           → minimap2
  │           └── other                 → blastn
  │
  ├── mode in {blastp, blastx, tblastn}
  │     └── get_backend(mode, tool=mode)   # pass tool to distinguish protein search
  │
  └── mode == "minimap2"
        └── backend.find(query, target, ...)  # uses db_path instead of db_prefix
```

ReadMapper works the same way: FASTA reads → minimap2, FASTQ reads → bwa.

## How gene_scanner Delegates

`gene_scanner.py` (420 lines) is the general-purpose gene scanning engine, supporting 9 databases
(card / vfdb / ecoh / plasmidfinder / resfinder / ncbi / megares / victors / ecoli_vf). It does **not call blastn directly**; instead it
delegates to `engine.SequenceMatcher`:

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

Likewise, `ecoh_serotyper.py`, `species_identifier.py`, and `shigella_serotyper.py` all invoke the underlying BLAST through `SequenceMatcher`, with zero code duplication.

## Extending with a New Backend

Adding a new alignment tool (e.g., Diamond) takes only two steps:

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

After that, `SequenceMatcher.match(query, db_prefix, mode="diamond")` just works.

## 7 Registered Backends

| Backend | Class | File | Purpose | Output |
|---|---|---|---|---|
| blastn | BlastBackend | blast.py | Nucleotide sequence search | list[Hit] |
| blastp | BlastBackend | blast.py | Protein sequence search | list[Hit] |
| blastx | BlastBackend | blast.py | Translated search | list[Hit] |
| tblastn | BlastBackend | blast.py | Reverse translated search | list[Hit] |
| minimap2 | MinimapBackend | minimap2.py | Assembly vs reference alignment | list[Hit] (PAF) |
| mash | MashBackend | kmer.py | MinHash genome distance estimation | list[KmerDistance] |
| sourmash | SourmashBackend | kmer.py | MinHash genome distance estimation | list[KmerDistance] |

### K-mer backends (mash / sourmash)

`kmer.py` provides MinHash genome distance estimation, suitable for rapid species identification and genome similarity screening:

```python
from hermes_bacmap.engine.backends import get_backend

mash = get_backend("mash")

# 创建 sketch
mash.sketch(Path("genome.fasta"), Path("genome.msh"))

# 计算距离
results = mash.distance(Path("query.msh"), Path("ref.msh"))
for r in results:
    print(f"{r.reference_id}: distance={r.distance}, shared={r.shared_hashes}")
```

The `KmerDistance` dataclass contains `distance`, `pvalue`, `shared_hashes`, and `total_hashes`.

### gene_synonyms gene-name normalization

`gene_scanner.py` provides `normalize_synonyms()` and `resolve_gene_name()` to handle gene-name aliases:

```python
from hermes_bacmap.analysis.gene_scanner import normalize_synonyms, resolve_gene_name

syn = normalize_synonyms({"stx1": ["stx1a", "stxA1"]})
resolve_gene_name("stx1a", syn)  # → "stx1"
```

Two input formats are supported: `{canonical: [aliases]}` and `{alias: canonical}`.

### Shared Utility Functions

`utils.py` (project level) provides parsing functions reused across modules:

| Function | Purpose | Duplicated code replaced |
|---|---|---|
| `parse_mlst(tsv)` | MLST TSV → {st, alleles} | 7 duplicate implementations |
| `parse_abricate_tsv(tsv)` | abricate TSV → list[dict] | 3 duplicate implementations |
| `read_json_file(path)` | JSON file reading + exception handling | 5+ duplicate implementations |

## Related

- [GOM data model](gom.en.md) — Hit results are ultimately serialized into `payload_json`
- [Snakemake pipeline](pipeline.en.md) — pipeline rules use the engine indirectly via the `bio_gene_scan` Hermes tool
- [Tool list](../reference/tools.md) — of the 24 tools, `bio_blast` / `bio_align` / `bio_gene_scan` are all engine-based
