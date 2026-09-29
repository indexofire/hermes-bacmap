"""Pan-genome discovery via MMseqs2 clustering.

Extracts CDS protein sequences from per-sample annotation.json files,
clusters them with mmseqs easy-linclust, and builds a cluster x sample
presence/absence matrix exported as Parquet for DuckDB federated queries.
Sequence IDs carry genome attribution as ``{sample}__{locus_tag}``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..engine.backends.mmseqs2 import Mmseqs2Backend, parse_cluster_tsv

SEQ_ID_SEP = "__"
_NOVEL_TOP_N = 20


@dataclass
class PangenomeResult:
    samples: list[str] = field(default_factory=list)
    total_sequences: int = 0
    total_clusters: int = 0
    core_clusters: int = 0
    accessory_clusters: int = 0
    unique_clusters: int = 0
    novel_clusters: list[dict[str, Any]] = field(default_factory=list)
    matrix_path: str = ""
    min_seq_id: float = 0.9
    coverage: float = 0.8
    method: str = "mmseqs2_linclust"

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_type": "pangenome",
            "method": self.method,
            "database": {"name": "mmseqs2_easy-linclust", "version": "unknown"},
            "samples": self.samples,
            "result": {
                "total_sequences": self.total_sequences,
                "total_clusters": self.total_clusters,
                "core_clusters": self.core_clusters,
                "accessory_clusters": self.accessory_clusters,
                "unique_clusters": self.unique_clusters,
                "novel_clusters": self.novel_clusters,
                "matrix_path": self.matrix_path,
                "min_seq_id": self.min_seq_id,
                "coverage": self.coverage,
            },
        }


def extract_proteins(results_dir: Path, samples: list[str]) -> tuple[Path, dict[str, str], int]:
    missing = [
        s for s in samples if not (results_dir / s / "annotation" / "annotation.json").exists()
    ]
    if missing:
        raise ValueError(
            f"annotation.json not found for: {', '.join(missing)} (run bio_analyze_pathogen first)"
        )

    fasta_path = results_dir / "pangenome" / "all_proteins.faa"
    fasta_path.parent.mkdir(parents=True, exist_ok=True)

    named: dict[str, str] = {}
    total = 0
    with fasta_path.open("w") as out:
        for sample in samples:
            data = json.loads((results_dir / sample / "annotation" / "annotation.json").read_text())
            for feature in data.get("features", []):
                if feature.get("ftype") != "CDS":
                    continue
                protein = feature.get("protein_seq", "")
                if not protein:
                    continue
                locus = feature.get("locus_tag") or f"cds_{total:04d}"
                seq_id = f"{sample}{SEQ_ID_SEP}{locus}"
                out.write(f">{seq_id}\n{protein}\n")
                if feature.get("gene"):
                    named[seq_id] = feature["gene"]
                total += 1
    return fasta_path, named, total


def build_matrix(
    clusters: dict[str, list[str]], samples: list[str], named: dict[str, str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rep, members in clusters.items():
        member_samples = {m.split(SEQ_ID_SEP)[0] for m in members if SEQ_ID_SEP in m}
        row: dict[str, Any] = {
            "representative": rep,
            "n_genomes": len(member_samples),
        }
        for sample in samples:
            row[sample] = 1 if sample in member_samples else 0
        names = {named[m] for m in members if m in named}
        row["named_gene"] = sorted(names)[0] if names else ""
        row["is_novel"] = not names
        rows.append(row)

    rows.sort(key=lambda r: (-r["n_genomes"], r["representative"]))
    for i, row in enumerate(rows, start=1):
        row["cluster_id"] = f"cluster_{i:04d}"
    return rows


def export_parquet(rows: list[dict[str, Any]], path: Path) -> None:
    import duckdb

    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_bytes(b"")
        return

    columns = list(rows[0].keys())
    con = duckdb.connect()
    con.execute(f"CREATE TABLE matrix ({', '.join(_duckdb_col(c, rows[0][c]) for c in columns)})")
    for row in rows:
        values = ", ".join(_duckdb_val(row[c]) for c in columns)
        con.execute(f"INSERT INTO matrix VALUES ({values})")
    con.execute(f"COPY matrix TO '{path}' (FORMAT PARQUET)")
    con.close()


def _duckdb_col(name: str, value: Any) -> str:
    if isinstance(value, bool):
        return f'"{name}" BOOLEAN'
    if isinstance(value, int):
        return f'"{name}" INTEGER'
    return f'"{name}" VARCHAR'


def _duckdb_val(value: Any) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def run_pangenome(
    samples: list[str],
    results_dir: Path,
    out_dir: Path | None = None,
    min_seq_id: float = 0.9,
    coverage: float = 0.8,
    threads: int = 4,
) -> PangenomeResult:
    fasta, named, total = extract_proteins(results_dir, samples)

    work_dir = out_dir or (results_dir / "pangenome")
    work_dir.mkdir(parents=True, exist_ok=True)
    prefix = work_dir / "clusters"

    backend = Mmseqs2Backend(threads=threads)
    tsv = backend.cluster(fasta, prefix, min_seq_id=min_seq_id, coverage=coverage)
    clusters = parse_cluster_tsv(tsv)

    rows = build_matrix(clusters, samples, named)
    matrix_path = work_dir / "presence_matrix.parquet"
    export_parquet(rows, matrix_path)

    n = len(samples)
    core = sum(1 for r in rows if r["n_genomes"] == n)
    unique = sum(1 for r in rows if r["n_genomes"] == 1)
    accessory = len(rows) - core - unique
    novel_rows = [r for r in rows if r["is_novel"]]

    result = PangenomeResult(
        samples=samples,
        total_sequences=total,
        total_clusters=len(rows),
        core_clusters=core,
        accessory_clusters=accessory,
        unique_clusters=unique,
        novel_clusters=[
            {
                "cluster_id": r["cluster_id"],
                "representative": r["representative"],
                "n_genomes": r["n_genomes"],
                "samples": [s for s in samples if r[s] == 1],
            }
            for r in novel_rows[:_NOVEL_TOP_N]
        ],
        matrix_path=str(matrix_path),
        min_seq_id=min_seq_id,
        coverage=coverage,
    )

    summary_path = work_dir / "summary.json"
    summary_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
