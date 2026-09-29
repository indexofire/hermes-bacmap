"""L2 sandbox tool handlers — code execution, GOM SQL, plotting.

bio_sandbox_exec runs AI-written Python in a subprocess sandbox with
session persistence; bio_sql_query issues read-only SELECT/WITH against the
GOM SQLite database; bio_plot renders quick charts to results/plots/.
Sandbox outputs enter reports only after user sign-off (project.md §L2).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ._common import _DEFAULT_DB_PATH, _RESULTS_DIR, logger, tool_handler

_MAX_ROWS = 100


@tool_handler
def sandbox_exec(args: dict[str, Any], **kwargs: Any) -> str:
    """Execute Python code in the L2 sandbox (session-persistent, timeout)."""
    code = str(args.get("code", ""))
    session = str(args.get("session", "default") or "default")
    timeout = int(args.get("timeout", 60) or 60)

    if not code.strip():
        return json.dumps({"error": "code is required"})

    try:
        from ..analysis.sandbox import exec_code

        result = exec_code(
            code,
            session=session,
            timeout=timeout,
            results_dir=Path(_RESULTS_DIR),
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("sandbox_exec failed")
        return json.dumps({"error": f"sandbox_exec failed: {e}"})


@tool_handler
def sql_query(args: dict[str, Any], **kwargs: Any) -> str:
    """Run a read-only SQL query against the GOM SQLite database."""
    sql = str(args.get("sql", "")).strip()
    db_path = Path(_DEFAULT_DB_PATH)

    if not db_path.exists():
        return json.dumps(
            {"error": f"GOM database not found at {db_path} — run ingest first"}
        )

    from ..analysis.analytics import _is_readonly_sql

    if not sql:
        return _core_tables(db_path)
    if not _is_readonly_sql(sql):
        return json.dumps(
            {"error": "only single read-only SELECT/WITH statements are allowed"}
        )

    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
        con.row_factory = sqlite3.Row
        cur = con.execute(sql)
        header = [d[0] for d in cur.description]
        rows = cur.fetchmany(_MAX_ROWS)
        truncated = len(rows) == _MAX_ROWS and cur.fetchone() is not None
        con.close()
    except sqlite3.Error as e:
        return json.dumps({"error": f"SQL error: {e}"})

    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        lines.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    if truncated:
        lines.append(f"(truncated at {_MAX_ROWS} rows)")
    return "\n".join(lines)


def _core_tables(db_path: Path) -> str:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
    tables = [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        if not r[0].startswith(("sqlite_", "fts_"))
    ]
    con.close()
    return (
        "GOM tables: "
        + ", ".join(tables)
        + " — retry with sql='SELECT ...' (read-only). "
        "Key tables: genome_objects (object_id, strain_id, object_type, "
        "payload_json, version), events (object_id, event_type, created_at), "
        "file_artifacts, strain_metadata, lab_results."
    )


@tool_handler
def plot(args: dict[str, Any], **kwargs: Any) -> str:
    """Render a quick chart (bar/line/scatter/hist/heatmap) to results/plots/."""
    spec = {
        "type": args.get("type", ""),
        "name": args.get("name", ""),
        "title": args.get("title", ""),
        "xlabel": args.get("xlabel", ""),
        "ylabel": args.get("ylabel", ""),
    }
    for key in ("labels", "values", "x", "y", "bins", "matrix", "row_labels", "col_labels"):
        if key in args:
            spec[key] = args[key]

    try:
        from ..analysis.plotting import make_plot

        result = make_plot(spec)
        return json.dumps(result, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception:
        logger.exception("plot failed")
        return json.dumps({"error": "plot failed — for bespoke figures use bio_sandbox_exec"})
