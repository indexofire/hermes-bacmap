"""Unit tests for quick plotting (analysis/plotting.py).

matplotlib Agg backend renders to PNG under results/plots/; five chart
types validated by file existence + non-empty content + PNG magic bytes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

matplotlib = pytest.importorskip("matplotlib", reason="matplotlib not installed")

from hermes_bacmap.analysis.plotting import make_plot  # noqa: E402


def _is_png(p: Path) -> bool:
    return p.exists() and p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


class TestMakePlot:
    def test_bar_chart(self, tmp_path):
        out = make_plot(
            {
                "type": "bar",
                "labels": ["tdh", "tlh", "trh"],
                "values": [12, 8, 3],
                "title": "Gene counts",
            },
            out_dir=tmp_path,
        )

        assert _is_png(Path(out["path"]))
        assert out["chart_type"] == "bar"
        assert out["n_points"] == 3

    def test_line_chart(self, tmp_path):
        out = make_plot(
            {"type": "line", "x": [1, 2, 3], "y": [10, 40, 90], "xlabel": "x"},
            out_dir=tmp_path,
        )
        assert _is_png(Path(out["path"]))

    def test_scatter_chart(self, tmp_path):
        out = make_plot(
            {"type": "scatter", "x": [1.5, 2.5], "y": [0.5, 0.9]},
            out_dir=tmp_path,
        )
        assert _is_png(Path(out["path"]))

    def test_histogram(self, tmp_path):
        out = make_plot(
            {"type": "hist", "values": [1, 2, 2, 3, 3, 3, 10], "bins": 4},
            out_dir=tmp_path,
        )
        assert _is_png(Path(out["path"]))

    def test_heatmap(self, tmp_path):
        out = make_plot(
            {
                "type": "heatmap",
                "matrix": [[1, 0, 1], [0, 1, 0]],
                "row_labels": ["geneA", "geneB"],
                "col_labels": ["S1", "S2", "S3"],
            },
            out_dir=tmp_path,
        )
        assert _is_png(Path(out["path"]))

    def test_unknown_type_raises(self, tmp_path):
        with pytest.raises(ValueError, match="type"):
            make_plot({"type": "pie3d", "values": [1]}, out_dir=tmp_path)

    def test_missing_required_data_raises(self, tmp_path):
        with pytest.raises(ValueError, match="labels"):
            make_plot({"type": "bar", "values": [1]}, out_dir=tmp_path)

    def test_filename_sanitized(self, tmp_path):
        out = make_plot(
            {"type": "bar", "labels": ["a"], "values": [1], "name": "../evil/../plot"},
            out_dir=tmp_path,
        )
        assert ".." not in Path(out["path"]).name
        assert Path(out["path"]).parent == tmp_path
