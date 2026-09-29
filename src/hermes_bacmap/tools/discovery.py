"""Discovery-layer tool handlers — pan-genome mining and federated analytics.

bio_pangenome clusters CDS proteins across genomes (mmseqs2) into a
presence/absence matrix; bio_analytics_query runs read-only DuckDB SQL over
existing result files; bio_differential_genes performs Fisher-exact
enrichment between two strain groups.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._common import _RESULTS_DIR, _validate_sample_id, logger, tool_handler


def _discover_annotated_samples(results_dir: Path) -> list[str]:
    return sorted({p.parent.parent.name for p in results_dir.glob("*/annotation/annotation.json")})


def _resolve_samples(requested: list[str], results_dir: Path) -> list[str] | str:
    samples = requested or _discover_annotated_samples(results_dir)
    if not samples:
        return json.dumps(
            {
                "error": "no annotated samples found — run bio_analyze_pathogen first "
                f"(looked for {results_dir}/*/annotation/annotation.json)"
            }
        )
    for sample in samples:
        if not _validate_sample_id(sample):
            return json.dumps({"error": f"invalid sample id: {sample!r}"})
    return samples


@tool_handler
def pangenome(args: dict[str, Any], **kwargs: Any) -> str:
    """Cluster CDS proteins across genomes into a presence/absence matrix."""
    samples = args.get("samples") or []
    min_seq_id = args.get("min_seq_id", 0.9)
    coverage = args.get("coverage", 0.8)
    threads = args.get("threads", 4)

    results_dir = Path(_RESULTS_DIR)
    resolved = _resolve_samples(list(samples), results_dir)
    if isinstance(resolved, str):
        return resolved
    if len(resolved) < 2:
        return json.dumps({"error": "pangenome needs >= 2 annotated samples", "samples": resolved})

    try:
        from ..analysis.pangenome import run_pangenome

        result = run_pangenome(
            resolved,
            results_dir,
            None,
            min_seq_id=float(min_seq_id),
            coverage=float(coverage),
            threads=int(threads),
        )
        return json.dumps(result.to_dict(), ensure_ascii=False)
    except (RuntimeError, ValueError) as e:
        return json.dumps({"error": f"pangenome failed: {e}"})
    except Exception:
        logger.exception("pangenome failed")
        return json.dumps({"error": "pangenome failed unexpectedly"})


@tool_handler
def analytics_query(args: dict[str, Any], **kwargs: Any) -> str:
    """Run a read-only DuckDB SQL query over existing analysis result files."""
    sql = str(args.get("sql", "")).strip()
    if not sql:
        return json.dumps({"error": "sql is required"})

    try:
        from ..analysis.analytics import query

        return query(sql, Path(_RESULTS_DIR))
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception:
        logger.exception("analytics_query failed")
        return json.dumps({"error": f"analytics_query failed for SQL: {sql[:200]}"})


@tool_handler
def differential_genes(args: dict[str, Any], **kwargs: Any) -> str:
    """Find genes enriched in one strain group versus another (Fisher exact)."""
    group_a = list(args.get("group_a") or [])
    group_b = list(args.get("group_b") or [])
    source = str(args.get("source", "gapit_card"))
    min_identity = args.get("min_identity", 80.0)
    min_prev_a = args.get("min_prev_a", 0.0)
    max_prev_b = args.get("max_prev_b", 1.0)

    if not group_a or not group_b:
        return json.dumps({"error": "group_a and group_b (strain id lists) are both required"})
    for sample in group_a + group_b:
        if not _validate_sample_id(sample):
            return json.dumps({"error": f"invalid sample id: {sample!r}"})

    try:
        from ..analysis.analytics import differential_genes as run_diff

        result = run_diff(
            group_a=group_a,
            group_b=group_b,
            source=source,
            results_dir=Path(_RESULTS_DIR),
            min_identity=float(min_identity),
            min_prev_a=float(min_prev_a),
            max_prev_b=float(max_prev_b),
        )
        _persist_differential(result.to_dict(), source, Path(_RESULTS_DIR))
        return json.dumps(result.to_dict(), ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception:
        logger.exception("differential_genes failed")
        return json.dumps({"error": "differential_genes failed unexpectedly"})


def _persist_differential(payload: dict[str, Any], source: str, results_dir: Path) -> None:
    out = results_dir / "analytics" / f"differential_{source}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
