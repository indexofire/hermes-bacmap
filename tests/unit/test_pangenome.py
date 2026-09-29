"""Unit tests for pan-genome discovery (analysis/pangenome.py).

Mmseqs2Backend is mocked at the class boundary; annotation.json inputs are
synthetic fixtures on tmp_path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.analysis.pangenome import (  # noqa: E402
    build_matrix,
    export_parquet,
    extract_proteins,
    run_pangenome,
)

_MOD = "hermes_bacmap.analysis.pangenome"


def _annotation(sample_id: str, features: list[dict]) -> str:
    return json.dumps(
        {
            "sample_id": sample_id,
            "contigs": [{"id": "ctg1", "length": 1000, "gc_content": 0.5}],
            "features": features,
            "summary": {"total_CDS": len(features)},
        }
    )


def _cds(locus: str, gene: str, protein: str = "MKVLAAAA") -> dict:
    return {
        "locus_tag": locus,
        "ftype": "CDS",
        "contig": "ctg1",
        "start": 1,
        "end": 100,
        "strand": 1,
        "length_bp": 100,
        "gene": gene,
        "product": f"product of {gene or locus}",
        "protein_seq": protein,
    }


def _make_annotation_file(results_dir: Path, sample: str, features: list[dict]) -> None:
    p = results_dir / sample / "annotation" / "annotation.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_annotation(sample, features))


class TestExtractProteins:
    def test_extracts_sample_prefixed_fasta_and_named_map(self, tmp_path):
        _make_annotation_file(
            tmp_path, "SAM1", [_cds("cds001", "gapA"), _cds("cds002", "", "MNOVCCCC")]
        )
        _make_annotation_file(
            tmp_path, "SAM2", [_cds("cds010", "tdh", "MTDH"), _cds("cds011", "")]
        )

        fasta, named, total = extract_proteins(tmp_path, ["SAM1", "SAM2"])

        text = fasta.read_text()
        assert ">SAM1__cds001" in text
        assert ">SAM1__cds002" in text
        assert ">SAM2__cds010" in text
        assert ">SAM2__cds011" in text
        assert "MKVLAAAA" in text and "MTDH" in text
        assert named == {"SAM1__cds001": "gapA", "SAM2__cds010": "tdh"}
        assert total == 4

    def test_skips_features_without_protein(self, tmp_path):
        no_protein = _cds("cds001", "gapA", protein="")
        _make_annotation_file(tmp_path, "SAM1", [no_protein])

        fasta, named, total = extract_proteins(tmp_path, ["SAM1"])

        assert ">SAM1__" not in fasta.read_text()
        assert total == 0

    def test_missing_annotation_raises_with_sample_list(self, tmp_path):
        with pytest.raises(ValueError, match="SAM2"):
            extract_proteins(tmp_path, ["SAM1", "SAM2"])


class TestBuildMatrix:
    def test_builds_rows_with_presence_and_novelty(self):
        clusters = {
            "SAM1__cds001": ["SAM1__cds001", "SAM2__cds010", "SAM3__cds005"],
            "SAM1__cds002": ["SAM1__cds002"],
            "SAM3__cds007": ["SAM3__cds007", "SAM1__cds020"],
        }
        named = {"SAM1__cds001": "gapA", "SAM2__cds010": "gapA"}

        rows = build_matrix(clusters, ["SAM1", "SAM2", "SAM3"], named)

        by_rep = {r["representative"]: r for r in rows}
        shared = by_rep["SAM1__cds001"]
        assert shared["n_genomes"] == 3
        assert shared["named_gene"] == "gapA"
        assert shared["is_novel"] is False
        assert shared["SAM1"] == 1 and shared["SAM2"] == 1 and shared["SAM3"] == 1

        unique = by_rep["SAM1__cds002"]
        assert unique["n_genomes"] == 1
        assert unique["is_novel"] is True
        assert unique["named_gene"] == ""

        partial = by_rep["SAM3__cds007"]
        assert partial["n_genomes"] == 2
        assert partial["is_novel"] is True

    def test_rows_sorted_by_genome_count_desc(self):
        clusters = {
            "SAM1__a": ["SAM1__a"],
            "SAM1__b": ["SAM1__b", "SAM2__b", "SAM3__b"],
        }
        rows = build_matrix(clusters, ["SAM1", "SAM2", "SAM3"], {})
        assert rows[0]["n_genomes"] >= rows[-1]["n_genomes"]

    def test_cluster_ids_are_stable_and_sequential(self):
        clusters = {"SAM1__a": ["SAM1__a", "SAM2__a"], "SAM1__b": ["SAM1__b"]}
        rows = build_matrix(clusters, ["SAM1", "SAM2"], {})
        ids = [r["cluster_id"] for r in rows]
        assert ids == [f"cluster_{i:04d}" for i in range(1, len(rows) + 1)]


class TestExportParquet:
    def test_parquet_roundtrip_via_duckdb(self, tmp_path):
        duckdb = pytest.importorskip("duckdb")
        rows = [
            {
                "cluster_id": "cluster_0001",
                "representative": "SAM1__a",
                "named_gene": "gapA",
                "is_novel": False,
                "n_genomes": 2,
                "SAM1": 1,
                "SAM2": 1,
            }
        ]
        out = tmp_path / "matrix.parquet"

        export_parquet(rows, out)

        con = duckdb.connect()
        n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
        assert n == 1
        row = con.execute(f"SELECT named_gene, is_novel FROM read_parquet('{out}')").fetchone()
        assert row == ("gapA", False)


class TestRunPangenome:
    def test_full_pipeline_with_mocked_backend(self, tmp_path):
        _make_annotation_file(tmp_path, "SAM1", [_cds("cds001", "gapA"), _cds("cds002", "")])
        _make_annotation_file(tmp_path, "SAM2", [_cds("cds010", "gapA")])

        def fake_cluster(fasta, out_prefix, min_seq_id=0.9, coverage=0.8):
            tsv = Path(f"{out_prefix}_cluster.tsv")
            tsv.write_text(
                "SAM1__cds001\tSAM1__cds001\n"
                "SAM1__cds001\tSAM2__cds010\n"
                "SAM1__cds002\tSAM1__cds002\n"
            )
            return tsv

        with patch(f"{_MOD}.Mmseqs2Backend") as backend_cls:
            backend_cls.return_value.cluster = fake_cluster
            result = run_pangenome(["SAM1", "SAM2"], tmp_path, tmp_path / "pangenome")

        assert result.samples == ["SAM1", "SAM2"]
        assert result.total_sequences == 3
        assert result.total_clusters == 2
        assert result.core_clusters == 1
        assert result.unique_clusters == 1
        assert len(result.novel_clusters) == 1
        assert result.novel_clusters[0]["n_genomes"] == 1
        assert Path(result.matrix_path).exists()

        d = result.to_dict()
        assert d["analysis_type"] == "pangenome"
        assert d["method"] == "mmseqs2_linclust"
        assert d["result"]["total_clusters"] == 2

    def test_returns_error_dict_when_annotation_missing(self, tmp_path):
        with pytest.raises(ValueError, match="annotation.json"):
            run_pangenome(["SAMX"], tmp_path, tmp_path / "pangenome")
