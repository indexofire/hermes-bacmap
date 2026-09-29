"""DuckDB federated analytics over existing analysis result files.

Zero-index design: no data is copied or pre-indexed into GOM. DuckDB reads
gapit TSVs, sample directories, and pangenome Parquet matrices directly
with columnar scans, so cross-genome queries stay cheap while results stay
on disk as the single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, lgamma
from pathlib import Path
from typing import Any

_FORBIDDEN_KEYWORDS = (
    "copy",
    "create",
    "insert",
    "delete",
    "update",
    "drop",
    "alter",
    "attach",
    "install",
    "load",
    "export",
    "pragma",
    "call",
    "vacuum",
    "checkpoint",
)

_GAPIT_SOURCES = {
    "gapit_card": "amr/gapit_card.tsv",
    "gapit_vfdb": "amr/gapit_vfdb.tsv",
    "gapit_plasmidfinder": "plasmid/gapit_plasmidfinder.tsv",
}


def _is_readonly_sql(sql: str) -> bool:
    stripped = sql.strip().rstrip(";").strip()
    if ";" in stripped:
        return False
    first = stripped.split(None, 1)[0].lower() if stripped else ""
    if first not in ("select", "with"):
        return False
    lowered = f" {stripped.lower()} "
    return not any(f" {kw} " in lowered for kw in _FORBIDDEN_KEYWORDS)


def _log_ncr(n: int, r: int) -> float:
    return lgamma(n + 1) - lgamma(r + 1) - lgamma(n - r + 1)


def _hyper_p(k: int, c1: int, r1: int, n: int) -> float:
    if k < 0 or k > c1 or r1 - k < 0 or r1 - k > n - c1:
        return 0.0
    return exp(_log_ncr(c1, k) + _log_ncr(n - c1, r1 - k) - _log_ncr(n, r1))


def _fisher_exact(a: int, b: int, c: int, d: int) -> float:
    r1, c1, n = a + b, a + c, a + b + c + d
    if n == 0:
        return 1.0
    p_obs = _hyper_p(a, c1, r1, n)
    lo = max(0, c1 - (n - r1))
    hi = min(c1, r1)
    total = sum(
        _hyper_p(k, c1, r1, n) for k in range(lo, hi + 1) if _hyper_p(k, c1, r1, n) <= p_obs
    )
    return min(1.0, total)


def _bh_adjust(pvals: list[float]) -> list[float]:
    n = len(pvals)
    if not n:
        return []
    order = sorted(range(n), key=lambda i: pvals[i])
    adjusted = [0.0] * n
    running = 1.0
    for rank in range(n, 0, -1):
        idx = order[rank - 1]
        running = min(running, pvals[idx] * n / rank, 1.0)
        adjusted[idx] = running
    return adjusted


def connect(results_dir: Path) -> Any:
    import duckdb

    con = duckdb.connect()

    for view_name, rel in _GAPIT_SOURCES.items():
        pattern = str(results_dir / "*" / rel.replace("/", "/"))
        if not list(results_dir.glob(f"*/{rel}")):
            continue
        con.execute(
            f"""
            CREATE VIEW {view_name} AS
            SELECT
                array_extract(string_split(filename, '/'), -3) AS strain_id,
                "GENE" AS gene,
                "%IDENTITY" AS identity,
                "%COVERAGE" AS coverage,
                "DATABASE" AS database,
                "PRODUCT" AS product
            FROM read_csv_auto('{pattern}', filename=true, header=true)
            """
        )

    sample_ids = sorted(
        {p.parent.parent.name for p in results_dir.glob("*/annotation/annotation.json")}
        | {
            p.parent.parent.name
            for rel in _GAPIT_SOURCES.values()
            for p in results_dir.glob(f"*/{rel}")
        }
    )
    if sample_ids:
        con.execute("CREATE TABLE samples (strain_id VARCHAR)")
        con.executemany("INSERT INTO samples VALUES (?)", [(s,) for s in sample_ids])

    matrix = results_dir / "pangenome" / "presence_matrix.parquet"
    if matrix.exists():
        con.execute(f"CREATE VIEW pangenome AS SELECT * FROM read_parquet('{matrix}')")

    return con


@dataclass
class DifferentialResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    group_a: list[str] = field(default_factory=list)
    group_b: list[str] = field(default_factory=list)
    source: str = ""
    min_identity: float = 80.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_type": "differential_genes",
            "method": "fisher_exact_bh",
            "source": self.source,
            "result": {
                "n_a": len(self.group_a),
                "n_b": len(self.group_b),
                "n_genes_tested": len(self.rows),
                "genes": self.rows,
            },
        }


def differential_genes(
    group_a: list[str],
    group_b: list[str],
    source: str,
    results_dir: Path,
    min_identity: float = 80.0,
    min_prev_a: float = 0.0,
    max_prev_b: float = 1.0,
) -> DifferentialResult:
    if not group_a or not group_b:
        raise ValueError("group_a and group_b must both be non-empty")

    con = connect(results_dir)
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if source not in views:
        raise ValueError(
            f"source view '{source}' not available (no result files?). "
            f"Available: {sorted(views) or 'none'}"
        )

    a_list = ", ".join(f"'{s.replace(chr(39), chr(39) * 2)}'" for s in group_a)
    b_list = ", ".join(f"'{s.replace(chr(39), chr(39) * 2)}'" for s in group_b)
    counts = con.execute(
        f"""
        SELECT gene,
               count(DISTINCT CASE WHEN strain_id IN ({a_list}) THEN strain_id END) AS present_a,
               count(DISTINCT CASE WHEN strain_id IN ({b_list}) THEN strain_id END) AS present_b
        FROM {source}
        WHERE identity >= {float(min_identity)}
        GROUP BY gene
        """
    ).fetchall()
    con.close()

    n_a, n_b = len(group_a), len(group_b)
    raw: list[dict[str, Any]] = []
    for gene, present_a, present_b in counts:
        p = _fisher_exact(present_a, n_a - present_a, present_b, n_b - present_b)
        prev_a = present_a / n_a
        prev_b = present_b / n_b
        raw.append(
            {
                "gene": gene,
                "present_a": present_a,
                "present_b": present_b,
                "prevalence_a": round(prev_a, 4),
                "prevalence_b": round(prev_b, 4),
                "fold_enrichment": round(prev_a / prev_b, 2) if prev_b > 0 else float("inf"),
                "p_value": p,
            }
        )

    q_values = _bh_adjust([r["p_value"] for r in raw])
    for row, q in zip(raw, q_values, strict=True):
        row["q_value"] = round(q, 6)

    rows = [r for r in raw if r["prevalence_a"] >= min_prev_a and r["prevalence_b"] <= max_prev_b]
    rows.sort(key=lambda r: (r["p_value"], -(r["present_a"])))

    return DifferentialResult(
        rows=rows,
        group_a=group_a,
        group_b=group_b,
        source=source,
        min_identity=min_identity,
    )


def query(sql: str, results_dir: Path, max_rows: int = 100) -> str:
    if not _is_readonly_sql(sql):
        raise ValueError("only single read-only SELECT/WITH statements are allowed")

    con = connect(results_dir)
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if not views:
        con.close()
        return (
            "no result views registered — run bio_analyze_pathogen and/or "
            "bio_pangenome first (expected files: */amr/gapit_*.tsv, "
            "*/annotation/annotation.json, pangenome/presence_matrix.parquet)"
        )

    cursor = con.execute(sql)
    header = [d[0] for d in cursor.description]
    rows = cursor.fetchmany(max_rows)
    truncated = len(rows) == max_rows and cursor.fetchone() is not None
    con.close()

    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        lines.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    if truncated:
        lines.append(f"(truncated at {max_rows} rows)")
    return "\n".join(lines)


def gene_prevalence(
    gene: str, source: str, results_dir: Path, min_identity: float = 80.0
) -> dict[str, Any]:
    con = connect(results_dir)
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if source not in views:
        raise ValueError(f"source view '{source}' not available. Available: {sorted(views)}")

    strains = [
        r[0]
        for r in con.execute(
            f"SELECT DISTINCT strain_id FROM {source} "
            f"WHERE gene = ? AND identity >= {float(min_identity)} ORDER BY strain_id",
            [gene],
        ).fetchall()
    ]
    total = con.execute("SELECT count(*) FROM samples").fetchone()[0]
    con.close()

    return {
        "gene": gene,
        "source": source,
        "present": len(strains),
        "total": total,
        "prevalence": round(len(strains) / total, 4) if total else 0.0,
        "strains_positive": strains,
    }
