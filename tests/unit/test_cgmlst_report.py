"""Tests for the cgMLST cohort report (plan todo 14).

Covers ``scripts/generate_report.py::generate_cgmlst_cohort_html`` (tree +
allele-distance heatmap rendering from a ``cgmlst_summary.json`` payload)
and the ``--group`` CLI helper functions (``_render_one_cgmlst_cohort`` and
``_render_cgmlst_cohort_groups``). Mirrors the fixture + assertion shape of
``tests/unit/test_cgmlst_cohort_ingest.py`` (the cgMLST cohort ingest tests):
a ``_make_cgmlst_summary`` builder + class-scoped test groups.

Importing ``generate_report`` from ``scripts/`` follows the sys.path
convention established in ``tests/unit/test_cgmlst_ingest.py:17-21``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import generate_report  # noqa: E402


def _make_cgmlst_summary(n_samples: int = 3) -> dict:
    """Build a minimal cgMLST cohort summary mirroring generate_cgmlst_summary.py.

    Golden pairwise distances (NOT computed by the impl under test): distance
    SAM-001<->SAM-002 = 5, SAM-001<->SAM-003 = 20, SAM-002<->SAM-003 = 11.
    These are used to assert the heatmap renders the right integers in the
    right cells.
    """
    samples = [f"SAM-{i:03d}" for i in range(1, n_samples + 1)]
    golden = {("SAM-001", "SAM-002"): 5, ("SAM-001", "SAM-003"): 20, ("SAM-002", "SAM-003"): 11}
    allele_distances: dict[str, int] = {}
    for i in range(len(samples)):
        for j in range(i + 1, len(samples)):
            a, b = samples[i], samples[j]
            allele_distances[f"{a}|{b}"] = golden.get((a, b), 1)
    return {
        "samples": samples,
        "n_samples": n_samples,
        "scheme": "senterica_2",
        "n_loci": 3002,
        "allele_distances": allele_distances,
        "tree_newick": f"({samples[0]}:0.01,{samples[1]}:0.02,{samples[2]}:0.03);",
        "missing_rate": 0.012,
        "thresholds_applied": {
            "outbreak_allele_dist": 10,
            "related_allele_dist": 100,
        },
        "group": "salmonella",
        "organism": "Salmonella enterica",
    }


# ---------------------------------------------------------------------------
# generate_cgmlst_cohort_html
# ---------------------------------------------------------------------------


class TestGenerateCgmlstCohortHtml:
    def test_writes_html_file_with_tree_and_heatmap(self, tmp_path: Path):
        summary = _make_cgmlst_summary()
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        assert out.exists()
        html = out.read_text(encoding="utf-8")
        # Tree widget + heatmap section both rendered.
        assert "cgmlst-tree-container" in html
        assert "等位基因距离矩阵" in html

    def test_reuses_phylotree_js_and_d3_v7_no_new_js_dep(self, tmp_path: Path):
        summary = _make_cgmlst_summary()
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        html = out.read_text(encoding="utf-8")
        # The exact SNP-cohort script tags must be reused (no new JS dep).
        assert "https://d3js.org/d3.v7.min.js" in html
        assert "raw.githack.com/rdvelin/phylotree.js/master/dist/phylotree.js" in html
        # And the exact Newick-agnostic rendering call.
        assert "d3.layout.phylotree()" in html

    def test_renders_scheme_n_loci_n_samples_stats(self, tmp_path: Path):
        summary = _make_cgmlst_summary()
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        html = out.read_text(encoding="utf-8")
        assert "senterica_2" in html
        assert "3,002" in html  # n_loci formatted with thousands sep
        # Sample count card + the three sample IDs in the heatmap header row.
        assert "SAM-001" in html
        assert "SAM-002" in html
        assert "SAM-003" in html

    def test_heatmap_renders_golden_allele_distances(self, tmp_path: Path):
        """Golden numbers (5/20/11) must appear in the upper-triangle cells.

        Asserts the cgMLST ``allele_distances`` payload flows through the same
        ``_distance_heatmap_html`` path the SNP report uses for its
        ``pairwise_distances``.
        """
        summary = _make_cgmlst_summary()
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        html = out.read_text(encoding="utf-8")
        assert ">5<" in html  # SAM-001 | SAM-002
        assert ">20<" in html  # SAM-001 | SAM-003
        assert ">11<" in html  # SAM-002 | SAM-003

    def test_fallback_newick_present_in_html(self, tmp_path: Path):
        """The raw Newick must be in the fallback div so the tree is visible
        even when phylotree.js fails to load (offline / CDN block)."""
        summary = _make_cgmlst_summary()
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        html = out.read_text(encoding="utf-8")
        assert summary["tree_newick"] in html

    def test_thresholds_block_rendered_when_present(self, tmp_path: Path):
        summary = _make_cgmlst_summary()
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        html = out.read_text(encoding="utf-8")
        assert "Applied thresholds" in html
        assert "outbreak_allele_dist" in html
        assert "10" in html
        assert "related_allele_dist" in html

    def test_thresholds_block_omitted_when_empty(self, tmp_path: Path):
        """V. parahaemolyticus ships UNVERIFIED (no numeric thresholds per
        plan todo 8); the block must be omitted cleanly, not rendered empty."""
        summary = _make_cgmlst_summary()
        summary["thresholds_applied"] = {}
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        html = out.read_text(encoding="utf-8")
        assert "Applied thresholds" not in html
        # The visible block (a <div class="cgmlst-thresholds">...</div>) must
        # not appear -- the bare CSS rule in <style> is fine to keep.
        assert '<div class="cgmlst-thresholds">' not in html

    def test_organism_in_title_when_present(self, tmp_path: Path):
        summary = _make_cgmlst_summary()
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        html = out.read_text(encoding="utf-8")
        assert "Salmonella enterica" in html

    def test_group_in_title(self, tmp_path: Path):
        summary = _make_cgmlst_summary()
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        html = out.read_text(encoding="utf-8")
        assert "[salmonella]" in html

    def test_missing_rate_rendered(self, tmp_path: Path):
        summary = _make_cgmlst_summary()
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        html = out.read_text(encoding="utf-8")
        # missing_rate=0.012 -> "1.2%" in the stats card.
        assert "1.2%" in html

    def test_empty_distances_renders_without_crash(self, tmp_path: Path):
        """A single-sample cohort has zero pairs; rendering must not divide
        by zero in the color gradient (max_d falls back to 1)."""
        summary = _make_cgmlst_summary()
        summary["samples"] = ["SAM-ONLY"]
        summary["n_samples"] = 1
        summary["allele_distances"] = {}
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        html = out.read_text(encoding="utf-8")
        assert "SAM-ONLY" in html
        assert "0" in html  # pair count stat

    def test_strips_unexpected_types_in_distances(self, tmp_path: Path):
        """JSON loading returns ``int`` for numeric values but defensive
        coercion must tolerate str-typed numbers (config-test edge case)."""
        summary = _make_cgmlst_summary()
        summary["allele_distances"] = {"SAM-001|SAM-002": "7"}
        out = tmp_path / "cohort_report.html"
        generate_report.generate_cgmlst_cohort_html(summary, out)
        html = out.read_text(encoding="utf-8")
        assert ">7<" in html


# ---------------------------------------------------------------------------
# _render_one_cgmlst_cohort
# ---------------------------------------------------------------------------


class TestRenderOneCgmlstCohort:
    def test_writes_html_and_returns_zero(self, tmp_path: Path, monkeypatch):
        results = tmp_path / "results"
        group_dir = results / "cgmlst" / "salmonella"
        group_dir.mkdir(parents=True)
        summary = _make_cgmlst_summary()
        (group_dir / "cgmlst_summary.json").write_text(json.dumps(summary))
        monkeypatch.setattr(generate_report, "RESULTS_DIR", results)

        rc = generate_report._render_one_cgmlst_cohort("salmonella")

        assert rc == 0
        out = group_dir / "cohort_report.html"
        assert out.exists()
        assert "cgMLST" in out.read_text(encoding="utf-8")

    def test_missing_summary_returns_one(self, tmp_path: Path, monkeypatch):
        results = tmp_path / "results"
        (results / "cgmlst" / "salmonella").mkdir(parents=True)
        monkeypatch.setattr(generate_report, "RESULTS_DIR", results)

        rc = generate_report._render_one_cgmlst_cohort("salmonella")

        assert rc == 1


# ---------------------------------------------------------------------------
# _render_cgmlst_cohort_groups (per-group iteration, mirrors ingest pattern)
# ---------------------------------------------------------------------------


class TestRenderCgmlstCohortGroups:
    def test_group_all_iterates_every_group_dir(self, tmp_path: Path, monkeypatch):
        """`--group all` mirrors ingest_results.py:248-268 per-group iteration:
        every results/cgmlst/<group>/cgmlst_summary.json gets its own report."""
        results = tmp_path / "results"
        cgmlst_root = results / "cgmlst"
        for group in ("salmonella", "ecoli", "vpara"):
            g = cgmlst_root / group
            g.mkdir(parents=True)
            summary = _make_cgmlst_summary()
            summary["group"] = group
            (g / "cgmlst_summary.json").write_text(json.dumps(summary))
        # An empty dir without a summary must be skipped silently.
        (cgmlst_root / "incomplete").mkdir()
        monkeypatch.setattr(generate_report, "RESULTS_DIR", results)

        rc = generate_report._render_cgmlst_cohort_groups("all")

        assert rc == 0
        for group in ("salmonella", "ecoli", "vpara"):
            out = cgmlst_root / group / "cohort_report.html"
            assert out.exists(), f"missing report for {group}"
        assert not (cgmlst_root / "incomplete" / "cohort_report.html").exists()

    def test_group_all_returns_one_when_no_dir(self, tmp_path: Path, monkeypatch):
        results = tmp_path / "results"
        monkeypatch.setattr(generate_report, "RESULTS_DIR", results)

        rc = generate_report._render_cgmlst_cohort_groups("all")

        assert rc == 1

    def test_group_all_returns_one_when_no_summaries(self, tmp_path: Path, monkeypatch):
        results = tmp_path / "results"
        (results / "cgmlst" / "empty").mkdir(parents=True)
        monkeypatch.setattr(generate_report, "RESULTS_DIR", results)

        rc = generate_report._render_cgmlst_cohort_groups("all")

        assert rc == 1

    def test_named_group_renders_single_group(self, tmp_path: Path, monkeypatch):
        results = tmp_path / "results"
        cgmlst_root = results / "cgmlst"
        for group in ("salmonella", "ecoli"):
            g = cgmlst_root / group
            g.mkdir(parents=True)
            summary = _make_cgmlst_summary()
            summary["group"] = group
            (g / "cgmlst_summary.json").write_text(json.dumps(summary))
        monkeypatch.setattr(generate_report, "RESULTS_DIR", results)

        rc = generate_report._render_cgmlst_cohort_groups("salmonella")

        assert rc == 0
        assert (cgmlst_root / "salmonella" / "cohort_report.html").exists()
        # Other group must not be rendered when a specific name is given.
        assert not (cgmlst_root / "ecoli" / "cohort_report.html").exists()
