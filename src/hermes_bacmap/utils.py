from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_mlst(mlst_tsv: str) -> dict[str, Any]:
    """Parse MLST TSV output into structured dict.

    Handles gmlst output format: header line + data line, tab-separated.
    Returns {"st": str, "alleles": {locus: allele}}.
    """
    if not mlst_tsv or mlst_tsv == "N/A":
        return {"st": "N/A", "alleles": {}}

    lines = mlst_tsv.strip().split("\n")
    if len(lines) < 2:
        return {"st": "N/A", "alleles": {}}

    header = lines[0].split("\t")
    data = lines[-1].split("\t")

    result: dict[str, Any] = {"alleles": {}}
    for i, col in enumerate(header):
        if i >= len(data):
            break
        col_lower = col.lower()
        if col_lower == "st":
            result["st"] = data[i]
        else:
            result["alleles"][col_lower] = data[i]

    if "st" not in result:
        result["st"] = data[-1] if data else "N/A"

    return result


def parse_abricate_tsv(tsv_text: str) -> list[dict[str, str]]:
    """Parse abricate-format TSV into list of dicts."""
    if not tsv_text:
        return []
    lines = tsv_text.strip().split("\n")
    if len(lines) < 2:
        return []
    header = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) >= len(header):
            rows.append(dict(zip(header, parts)))
    return rows


def read_json_file(path: str | Path) -> dict | None:
    """Read and parse a JSON file, return None if missing or invalid."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
