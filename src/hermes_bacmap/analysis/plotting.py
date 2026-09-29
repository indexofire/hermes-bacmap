"""Quick plotting — matplotlib Agg rendering for L2 exploration charts.

Renders bar/line/scatter/hist/heatmap specs to PNG under results/plots/.
Deterministic (no display), filename sanitized, returns the saved path.
For bespoke figures the AI should use bio_sandbox_exec instead.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_TYPES = ("bar", "line", "scatter", "hist", "heatmap")
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def make_plot(spec: dict[str, Any], out_dir: Path | None = None) -> dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    chart_type = str(spec.get("type", "")).lower()
    if chart_type not in _TYPES:
        raise ValueError(f"unsupported type {chart_type!r}; expected one of {_TYPES}")

    if out_dir is None:
        from ..config import RESULTS_DIR

        out_dir = RESULTS_DIR / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    name = _SAFE_NAME_RE.sub("_", str(spec.get("name") or chart_type))
    name = re.sub(r"\.\.+", "_", name).strip("._-")
    if not name:
        name = chart_type
    out_path = out_dir / f"{name}.png"

    fig, ax = plt.subplots(figsize=(8, 5))
    n_points = 0

    if chart_type == "bar":
        labels = spec.get("labels")
        values = spec.get("values")
        if not labels or values is None:
            raise ValueError("bar chart requires labels and values")
        ax.bar([str(x) for x in labels], [float(v) for v in values])
        n_points = len(values)
    elif chart_type == "line":
        x, y = spec.get("x"), spec.get("y")
        if x is None or y is None:
            raise ValueError("line chart requires x and y")
        ax.plot([float(v) for v in x], [float(v) for v in y], marker="o")
        n_points = len(x)
    elif chart_type == "scatter":
        x, y = spec.get("x"), spec.get("y")
        if x is None or y is None:
            raise ValueError("scatter chart requires x and y")
        ax.scatter([float(v) for v in x], [float(v) for v in y])
        n_points = len(x)
    elif chart_type == "hist":
        values = spec.get("values")
        if not values:
            raise ValueError("hist chart requires values")
        ax.hist([float(v) for v in values], bins=int(spec.get("bins", 20) or 20))
        n_points = len(values)
    else:
        matrix = spec.get("matrix")
        if not matrix or not matrix[0]:
            raise ValueError("heatmap requires matrix")
        ax.imshow(matrix, aspect="auto", cmap="Blues")
        row_labels = spec.get("row_labels") or [f"r{i}" for i in range(len(matrix))]
        col_labels = spec.get("col_labels") or [f"c{i}" for i in range(len(matrix[0]))]
        ax.set_xticks(range(len(col_labels)))
        ax.set_xticklabels(col_labels, rotation=45, ha="right")
        ax.set_yticks(range(len(row_labels)))
        ax.set_yticklabels(row_labels)
        n_points = len(matrix) * len(matrix[0])

    if spec.get("title"):
        ax.set_title(str(spec["title"]))
    if spec.get("xlabel"):
        ax.set_xlabel(str(spec["xlabel"]))
    if spec.get("ylabel"):
        ax.set_ylabel(str(spec["ylabel"]))

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    return {"path": str(out_path), "chart_type": chart_type, "n_points": n_points}
