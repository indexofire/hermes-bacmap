# GOM Data Model

The Genome Object Model (GOM) is the platform's **unified data standard**, defining the structure, lifecycle, versioning, and event model of all business objects.
Built on SQLite + WAL + FTS5 — a single file with zero operations overhead.

## Design Principles

| Principle | Implementation |
|---|---|
| **Document First** | All business objects are JSON documents stored in the `payload_json` column |
| **Event First** | The complete analysis process is recorded in the `events` table (uploaded → qc → ... → report) |
| **Version First** | `(object_id, version)` composite primary key, monotonically increasing versions |
| **Immutable** | `delete()` always raises; duplicate primary keys raise; updates can only create new versions |

## SQLite Table Schema

### 1. genome_objects (core object table)

```sql
CREATE TABLE genome_objects (
    object_id TEXT NOT NULL,           -- UUID v4
    object_type TEXT NOT NULL,          -- sample | analysis | report | workflow | ...
    version INTEGER NOT NULL,           -- 单调递增，从 1 开始
    schema_version TEXT NOT NULL,       -- semver "0.1.0"
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    payload_json TEXT NOT NULL,         -- 所有分析结果存于此 JSON
    organism TEXT,                      -- 索引字段（如 "Salmonella enterica"）
    strain_id TEXT,                     -- 索引字段（如 "SAM-TYP-001"）
    pipeline_version TEXT,              -- ANALYSIS 必填（证据链）
    database_signature TEXT,
    PRIMARY KEY (object_id, version)    -- 复合主键 → 版本化 + 不可变
);
```

Top-level fields (object_id / object_type / organism, etc.) are stored in dedicated columns for indexing;
payload / database_versions / tool_versions are serialized as JSON into `payload_json` and distinguished by the `__gom_` prefix.

### 2. genome_objects_fts (full-text search virtual table)

```sql
CREATE VIRTUAL TABLE genome_objects_fts USING fts5(
    object_type, organism, strain_id, payload_text
);
```

Supports BM25 full-text search and is the underlying engine of the `bio_search_samples` tool (field weighting with a degraded fallback score=1).

### 3. events (event stream)

```sql
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    event_type TEXT NOT NULL,           -- uploaded | qc_finished | ... | snp_finished
    event_payload TEXT NOT NULL,        -- JSON
    timestamp TEXT NOT NULL
);
```

Standard event lifecycle:

```
uploaded → qc_finished → assembly_finished → annotation_finished
  → amr_finished → mlst_finished → serotype_finished
  → snp_finished → report_generated → version_created (if re-analyzed)
```

### 4. file_artifacts (file artifact references)

```sql
CREATE TABLE file_artifacts (
    artifact_id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    file_type TEXT NOT NULL,            -- fastq | fasta | bam | vcf | gff | report
    file_path TEXT NOT NULL,            -- 本地绝对路径（V1.0+ 改 s3:// URI）
    sha256 TEXT NOT NULL,               -- 64 字符 hex，写入时实时校验
    size_bytes INTEGER NOT NULL
);
```

**Design principle**: the database stores only references; large files stay on the local FS.
`register_file_artifact()` automatically verifies at write time that the file exists and that SHA256 and size match.

## Indexes and PRAGMAs

```sql
CREATE INDEX idx_go_type     ON genome_objects(object_type);
CREATE INDEX idx_go_organism ON genome_objects(organism);
CREATE INDEX idx_go_strain   ON genome_objects(strain_id);
CREATE INDEX idx_events_obj  ON events(object_id, timestamp);
CREATE INDEX idx_fa_object   ON file_artifacts(object_id, version);
```

```sql
PRAGMA journal_mode = WAL;          -- 多读 + 单写不互斥
PRAGMA synchronous = NORMAL;        -- WAL 下仍 corruption-safe
PRAGMA mmap_size = 30000000000;     -- ~28 GB mmap
PRAGMA temp_store = MEMORY;
PRAGMA foreign_keys = ON;
```

## GOS Class API

`GenomeObjectService` (`genome_object_service.py`, 644 lines) is the sole public API:

| Category | Method | Description |
|---|---|---|
| CRUD | `create(obj)` | Create (duplicate primary key raises `GOMImmutableError`) |
| | `read(object_id, version)` | Read a specific version |
| | `list_by_type(object_type)` | List latest versions by type |
| | `list_by_organism(organism)` | Filter by organism |
| | `delete(...)` | **Always raises** (Immutable) |
| Version | `create_new_version(object_id, payload)` | Create v+1, inheriting metadata |
| | `get_latest_version(object_id)` | Get the latest version number |
| | `list_versions(object_id)` | List all versions (ascending) |
| File | `register_file_artifact(...)` | Register a file (with SHA256 verification) |
| | `list_file_artifacts(object_id)` | List associated files |
| Event | `log_event(object_id, type, payload)` | Log an event |
| | `list_events(object_id, since)` | List events (supports time filtering) |

Context manager usage:

```python
from pathlib import Path
from hermes_bacmap.services.genome_object_service import GenomeObjectService

with GenomeObjectService(Path("data/hermes_bacmap.sqlite")) as gos:
    obj = gos.create(my_genome_object)
    gos.log_event(obj.object_id, "uploaded", {"strain_id": "SAM-TYP-001"})
```

## Versioning and Deduplication

```
strain_id already exists?
├── No → create v1
├── Yes + same pipeline_version → skip (⏭️ avoid duplicates)
└── Yes + different pipeline_version → create a new version (Immutable + Version First)
```

`create_new_version` inheritance rules: object_id / object_type / schema_version / created_by / organism / strain_id are all inherited;
version is incremented by 1; created_at is set to the current time; payload uses the newly passed value.

## Triple Evidence Chain

Every ANALYSIS object must carry a triple evidence chain to satisfy public-health audit requirements:

```
strain_id:          SAM-TYP-001
pipeline_version:   salmonella-workflow-v0.1
database_versions:  CARD 2026-Apr-3, VFDB 2026-Apr-3,
                    PlasmidFinder 2026-Apr-3, PubMLST salmonella_2
tool_versions:      fastp 1.3.5, Shovill 1.1.0, blast 2.17.0+,
                    gmlst 0.1.0, SISTR 1.1.3, abricate 1.4.0
```

Storage locations: `pipeline_version` → dedicated column; `database_versions` / `tool_versions` → `__gom_`-prefixed keys inside `payload_json`.

## Cohort SNP Ingestion Design

SNP analysis is a **multi-sample (cohort-level)** result and cannot fit into a per-sample object. The solution is to create a cohort-level ANALYSIS object:

```python
GenomeObject(
    object_type="analysis",
    strain_id="cohort:salmonella-snp",        # 去重键前缀
    organism="Salmonella enterica",
    payload={
        "analysis_type": "snp_cohort",
        "samples": ["SAM-TYP-001", "SAM-TYP-002", ...],   # 7 株
        "tree_newick": "(SAM-TYP-001:0.005,...)",
        "pairwise_distances": {"SAM-TYP-001|SAM-TYP-002": 1666, ...},
        "n_snp_sites": 122598,
        "missing_rate": 0.0467,
    },
    pipeline_version="snp-pipeline-v0.3",
)
```

Each sample's ANALYSIS object additionally records an `snp_finished` event whose payload contains a reference to the cohort object_id, establishing a bidirectional link.

File artifact registration:

| file_type | File |
|---|---|
| `snp_tree_newick` | `core.treefile` |
| `snp_alignment` | `core_snps.fasta` |
| `iqtree_report` | `core.iqtree` |
| `joint_vcf` | `joint.vcf.gz` |
| `snp_summary` | `snp_summary.json` |

Ingestion commands:

```bash
python scripts/ingest_results.py --all     # 先入库单株
python scripts/ingest_results.py --snp     # 再入库 cohort
```

Idempotent: repeated ingestion with the same pipeline_version is skipped.

## Error Types

| Exception | Trigger scenario |
|---|---|
| `GOMValidationError` | Schema validation failure (object_type / version / schema_version / evidence chain) |
| `GOMNotFoundError` | Reading a non-existent (object_id, version) |
| `GOMImmutableError` | Overwriting an existing primary key or calling `delete()` |
| `FrozenInstanceError` | Modifying a frozen dataclass field |

## Migration Path

V1.0+ trigger conditions: ≥5 concurrent users, >100M metadata rows, complex KG reasoning. SQLite → PostgreSQL (`payload_json TEXT` → `jsonb`, FTS5 → `pg_trgm + tsvector`), migrated in one step with `pgloader`.
