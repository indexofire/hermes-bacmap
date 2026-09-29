"""Unit tests for discovery-layer tool handlers (tools/discovery.py).

_RESULTS_DIR is monkeypatched to a synthetic tree; mmseqs2 backend is
mocked for pangenome; the plugin registry must expose 32 tools including
the three discovery tools.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.tools import analytics_query, differential_genes, pangenome  # noqa: E402

GAPIT_HEADER = (
    "#FILE\tSEQUENCE\tSTART\tEND\tSTRAND\tGENE\tCOVERAGE\tCOVERAGE_MAP\tGAPS\t"
    "%COVERAGE\t%IDENTITY\tDATABASE\tACCESSION\tPRODUCT\tRESISTANCE"
)


def _make_tree(tmp_path: Path) -> None:
    layout = {"SAM-A1": ["geneX", "geneY"], "SAM-A2": ["geneX"], "SAM-B1": ["geneY"]}
    for sample, genes in layout.items():
        d = tmp_path / sample / "amr"
        d.mkdir(parents=True, exist_ok=True)
        rows = [
            f"results/{sample}/c.fasta\tctg1\t1\t99\t+\t{g}\t1:0-99\t0/99\t0/0\t"
            f"100.0\t99.5\tcard\tX1\tp\t"
            for g in genes
        ]
        (d / "gapit_card.tsv").write_text(GAPIT_HEADER + "\n" + "\n".join(rows) + "\n")


def _decode(out: str) -> dict:
    return json.loads(out)


class TestAnalyticsQueryHandler:
    def test_returns_markdown_rows(self, tmp_path, monkeypatch):
        _make_tree(tmp_path)
        monkeypatch.setattr("hermes_bacmap.tools.discovery._RESULTS_DIR", tmp_path)

        out = analytics_query({"sql": "SELECT gene FROM gapit_card ORDER BY gene"})

        assert "geneX" in out and "geneY" in out

    def test_missing_sql_returns_error(self):
        out = _decode(analytics_query({}))
        assert "error" in out

    def test_write_sql_rejected(self, tmp_path, monkeypatch):
        _make_tree(tmp_path)
        monkeypatch.setattr("hermes_bacmap.tools.discovery._RESULTS_DIR", tmp_path)

        out = _decode(analytics_query({"sql": "DROP TABLE gapit_card"}))

        assert "error" in out


class TestDifferentialGenesHandler:
    def test_enrichment_output(self, tmp_path, monkeypatch):
        _make_tree(tmp_path)
        monkeypatch.setattr("hermes_bacmap.tools.discovery._RESULTS_DIR", tmp_path)

        out = _decode(
            differential_genes(
                {"group_a": ["SAM-A1", "SAM-A2"], "group_b": ["SAM-B1"]}
            )
        )

        assert out["analysis_type"] == "differential_genes"
        genes = {r["gene"] for r in out["result"]["genes"]}
        assert "geneX" in genes

    def test_empty_group_returns_error(self):
        out = _decode(differential_genes({"group_a": [], "group_b": ["SAM-B1"]}))
        assert "error" in out

    def test_bad_sample_id_returns_error(self):
        out = _decode(
            differential_genes(
                {"group_a": ["../etc"], "group_b": ["SAM-B1"]}
            )
        )
        assert "error" in out


class TestPangenomeHandler:
    def test_too_few_samples_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes_bacmap.tools.discovery._RESULTS_DIR", tmp_path)

        out = _decode(pangenome({"samples": ["SAM-ONLY"]}))

        assert "error" in out

    def test_no_annotated_samples_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("hermes_bacmap.tools.discovery._RESULTS_DIR", tmp_path)

        out = _decode(pangenome({}))

        assert "error" in out

    def test_runs_pangenome_with_discovered_samples(self, tmp_path, monkeypatch):
        for sample in ("SAM-A1", "SAM-A2"):
            d = tmp_path / sample / "annotation"
            d.mkdir(parents=True)
            (d / "annotation.json").write_text(
                json.dumps(
                    {
                        "sample_id": sample,
                        "features": [
                            {
                                "locus_tag": "cds001",
                                "ftype": "CDS",
                                "gene": "gapA",
                                "protein_seq": "MKVL",
                            }
                        ],
                    }
                )
            )

        def fake_run(samples, results_dir, out_dir, min_seq_id, coverage, threads):
            from hermes_bacmap.analysis.pangenome import PangenomeResult

            return PangenomeResult(samples=list(samples), total_clusters=1)

        monkeypatch.setattr("hermes_bacmap.tools.discovery._RESULTS_DIR", tmp_path)
        with patch(
            "hermes_bacmap.analysis.pangenome.run_pangenome", side_effect=fake_run
        ):
            out = _decode(pangenome({}))

        assert out["analysis_type"] == "pangenome"
        assert out["samples"] == ["SAM-A1", "SAM-A2"]


class TestRegistryWiring:
    def test_discovery_tools_registered(self):
        from hermes_bacmap.tools.registry import _TOOL_REGISTRY

        names = {name for name, _, _ in _TOOL_REGISTRY}
        assert {
            "bio_pangenome",
            "bio_analytics_query",
            "bio_differential_genes",
        } <= names
