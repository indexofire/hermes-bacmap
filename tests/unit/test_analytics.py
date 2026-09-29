"""Unit tests for DuckDB federated analytics (analysis/analytics.py).

Synthetic results tree on tmp_path mimics pipeline outputs (abricate-format
gapit TSVs); Fisher exact and BH correction verified against hand-computed
values.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

duckdb = pytest.importorskip("duckdb", reason="duckdb not installed")

from hermes_bacmap.analysis.analytics import (  # noqa: E402
    _bh_adjust,
    _fisher_exact,
    _is_readonly_sql,
    connect,
    differential_genes,
    gene_prevalence,
)

GAPIT_HEADER = (
    "#FILE\tSEQUENCE\tSTART\tEND\tSTRAND\tGENE\tCOVERAGE\tCOVERAGE_MAP\tGAPS\t"
    "%COVERAGE\t%IDENTITY\tDATABASE\tACCESSION\tPRODUCT\tRESISTANCE"
)


def _gapit_row(file_label: str, gene: str, identity: float = 99.5) -> str:
    return (
        f"{file_label}\tctg1\t101\t900\t+\t{gene}\t1:0-799\t0/799\t0/0\t"
        f"100.0\t{identity}\tcard\tX001\tproduct of {gene}\t"
    )


def _make_results_tree(tmp_path: Path, group_a: list[str], group_b: list[str]) -> None:
    gene_layout = {
        "geneX": (group_a, []),
        "geneY": (group_a, group_b),
        "geneZ": ([], group_b),
        "geneWeak": (group_a[:1], group_b[:1]),
    }
    for gene, (in_a, in_b) in gene_layout.items():
        for sample in in_a + in_b:
            d = tmp_path / sample / "amr"
            d.mkdir(parents=True, exist_ok=True)
            tsv = d / "gapit_card.tsv"
            if not tsv.exists():
                tsv.write_text(GAPIT_HEADER + "\n")
            with tsv.open("a") as f:
                f.write(_gapit_row(f"results/{sample}/contigs.fasta", gene) + "\n")


_A = ["SAM-A1", "SAM-A2", "SAM-A3", "SAM-A4"]
_B = ["SAM-B1", "SAM-B2", "SAM-B3", "SAM-B4"]


class TestFisherExact:
    def test_perfect_separation_4v4(self):
        # [[4,0],[0,4]]: two-tailed p = 2/C(8,4) = 2/70
        assert _fisher_exact(4, 0, 0, 4) == pytest.approx(2 / 70)

    def test_no_association(self):
        assert _fisher_exact(4, 0, 4, 0) == pytest.approx(1.0)

    def test_symmetric(self):
        assert _fisher_exact(4, 0, 0, 4) == pytest.approx(_fisher_exact(0, 4, 4, 0))

    def test_degenerate_single_cell(self):
        assert _fisher_exact(1, 0, 0, 0) == pytest.approx(1.0)


class TestBHAdjust:
    def test_monotone_adjustment(self):
        p = [0.028571, 1.0, 0.028571]
        q = _bh_adjust(p)
        assert q[0] == pytest.approx(0.042857, abs=1e-5)
        assert q[2] == pytest.approx(0.042857, abs=1e-5)
        assert q[1] == pytest.approx(1.0)

    def test_empty(self):
        assert _bh_adjust([]) == []


class TestReadOnlyGuard:
    def test_allows_select_and_with(self):
        assert _is_readonly_sql("SELECT 1")
        assert _is_readonly_sql("with t as (select 1) select * from t")

    def test_rejects_write_statements(self):
        for sql in (
            "DELETE FROM gapit_card",
            "INSERT INTO t VALUES (1)",
            "COPY (SELECT 1) TO '/tmp/x.parquet'",
            "CREATE TABLE t (a int)",
            "ATTACH 'x.db' AS x",
            "select 1; drop table t",
        ):
            assert not _is_readonly_sql(sql)


class TestConnect:
    def test_registers_gapit_samples_and_strain_extraction(self, tmp_path):
        _make_results_tree(tmp_path, _A, _B)

        con = connect(tmp_path)

        n = con.execute("SELECT count(*) FROM gapit_card").fetchone()[0]
        assert n == 4 + 8 + 4 + 2
        strains = {
            r[0]
            for r in con.execute("SELECT DISTINCT strain_id FROM gapit_card").fetchall()
        }
        assert "SAM-A1" in strains and "SAM-B4" in strains
        n_samples = con.execute("SELECT count(*) FROM samples").fetchone()[0]
        assert n_samples == 8

    def test_missing_files_skip_view_creation(self, tmp_path):
        con = connect(tmp_path)
        views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        assert "gapit_card" not in views

    def test_pangenome_view_when_parquet_exists(self, tmp_path):
        from hermes_bacmap.analysis.pangenome import export_parquet

        _make_results_tree(tmp_path, _A, _B)
        export_parquet(
            [
                {
                    "cluster_id": "cluster_0001",
                    "representative": "SAM-A1__cds001",
                    "named_gene": "gapA",
                    "is_novel": False,
                    "n_genomes": 2,
                    "SAM-A1": 1,
                    "SAM-B1": 1,
                }
            ],
            tmp_path / "pangenome" / "presence_matrix.parquet",
        )

        con = connect(tmp_path)

        gene = con.execute(
            "SELECT named_gene FROM pangenome WHERE n_genomes = 2"
        ).fetchone()[0]
        assert gene == "gapA"


class TestDifferentialGenes:
    def test_enrichment_with_known_pvalues(self, tmp_path):
        _make_results_tree(tmp_path, _A, _B)

        result = differential_genes(
            group_a=_A, group_b=_B, source="gapit_card", results_dir=tmp_path
        )

        by_gene = {r["gene"]: r for r in result.rows}
        assert set(by_gene) == {"geneX", "geneY", "geneZ", "geneWeak"}

        gene_x = by_gene["geneX"]
        assert gene_x["present_a"] == 4 and gene_x["present_b"] == 0
        assert gene_x["p_value"] == pytest.approx(2 / 70, abs=1e-6)
        assert gene_x["q_value"] == pytest.approx(4 / 70, abs=1e-5)

        assert by_gene["geneY"]["p_value"] == pytest.approx(1.0)

        d = result.to_dict()
        assert d["analysis_type"] == "differential_genes"
        assert d["result"]["n_a"] == 4 and d["result"]["n_b"] == 4

    def test_prevalence_thresholds_filter_rows(self, tmp_path):
        _make_results_tree(tmp_path, _A, _B)

        result = differential_genes(
            group_a=_A,
            group_b=_B,
            source="gapit_card",
            results_dir=tmp_path,
            min_prev_a=0.9,
            max_prev_b=0.1,
        )

        genes = {r["gene"] for r in result.rows}
        assert genes == {"geneX"}

    def test_identity_filter_applied(self, tmp_path):
        _make_results_tree(tmp_path, _A, _B)
        low = tmp_path / "SAM-A1" / "amr" / "gapit_card.tsv"
        with low.open("a") as f:
            f.write(_gapit_row("results/SAM-A1/contigs.fasta", "geneLow", identity=60.0) + "\n")

        result = differential_genes(
            group_a=_A, group_b=_B, source="gapit_card", results_dir=tmp_path
        )

        assert "geneLow" not in {r["gene"] for r in result.rows}

    def test_missing_view_raises(self, tmp_path):
        with pytest.raises(ValueError, match="gapit_card"):
            differential_genes(
                group_a=_A, group_b=_B, source="gapit_card", results_dir=tmp_path
            )


class TestGenePrevalence:
    def test_prevalence_across_all_strains(self, tmp_path):
        _make_results_tree(tmp_path, _A, _B)

        result = gene_prevalence("geneX", source="gapit_card", results_dir=tmp_path)

        assert result["present"] == 4
        assert result["total"] == 8
        assert result["prevalence"] == pytest.approx(0.5)
        assert "SAM-A1" in result["strains_positive"]


class TestQuery:
    def test_query_returns_markdown_table(self, tmp_path):
        from hermes_bacmap.analysis.analytics import query

        _make_results_tree(tmp_path, _A, _B)

        out = query("SELECT gene, count(*) AS n FROM gapit_card GROUP BY gene", tmp_path)

        assert "geneX" in out and "geneWeak" in out
        assert out.count("|") >= 3

    def test_query_rejects_non_select(self, tmp_path):
        from hermes_bacmap.analysis.analytics import query

        with pytest.raises(ValueError, match="read-only"):
            query("DELETE FROM gapit_card", tmp_path)

    def test_query_lists_available_views_when_empty(self, tmp_path):
        from hermes_bacmap.analysis.analytics import query

        out = query("SELECT 1", tmp_path)

        assert "no result views" in out
