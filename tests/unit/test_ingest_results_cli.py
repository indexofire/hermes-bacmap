"""CLI dispatch tests for scripts/ingest_results.py (plan todo 15).

Verifies that --cgmlst-cohort dispatches to ``ingest_cohort_cgmlst`` and
that ``--all`` exercises both the mainline per-sample ingest and the
cgMLST per-sample ingest (the "SNP + cgMLST" umbrella coverage required
by todo 15's acceptance criteria). Todo 13 already wired the flag; these
tests lock the dispatch so it cannot regress.

Strategy: monkeypatch ``DB_PATH`` at a tmp SQLite file (so
GenomeObjectService constructs against a throwaway DB), stub the ingest
functions to record calls, set sys.argv, call main(), assert dispatch.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import _common  # noqa: E402
import ingest_results  # noqa: E402

_SAMPLES_TSV = (
    "sample\tspecies\tR1\tR2\n"
    "SAM-SAL-001\tSalmonella\tr1.fq\tr2.fq\n"
    "SAM-SAL-002\tSalmonella\tr1.fq\tr2.fq\n"
)


@pytest.fixture
def fake_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect DB + samples.tsv to tmp_path."""
    workflow_dir = tmp_path / "workflows" / "bacmap"
    config_dir = workflow_dir / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "samples.tsv").write_text(_SAMPLES_TSV)

    monkeypatch.setattr(ingest_results, "DB_PATH", tmp_path / "test.sqlite")
    monkeypatch.setattr(ingest_results, "ROOT", tmp_path)
    monkeypatch.setattr(ingest_results, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(_common, "ROOT", tmp_path)
    monkeypatch.setattr(_common, "SAMPLES_TSV", config_dir / "samples.tsv")
    return tmp_path


def _patch_argv(monkeypatch: pytest.MonkeyPatch, *argv: str) -> None:
    monkeypatch.setattr(sys, "argv", ["ingest_results.py", *argv])


class TestCgmlstCohortDispatch:
    def test_dispatches_to_ingest_cohort_cgmlst(
        self, fake_env: Path, monkeypatch: pytest.MonkeyPatch
    ):
        called: list[bool] = []

        def fake_ingest(gos):
            called.append(True)
            return ["oid-cohort-1"]

        monkeypatch.setattr(ingest_results, "ingest_cohort_cgmlst", fake_ingest)
        _patch_argv(monkeypatch, "--cgmlst-cohort")

        rc = ingest_results.main()
        assert rc == 0
        assert called == [True]

    def test_returns_nonzero_when_nothing_ingested(
        self, fake_env: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(ingest_results, "ingest_cohort_cgmlst", lambda gos: [])
        _patch_argv(monkeypatch, "--cgmlst-cohort")

        rc = ingest_results.main()
        assert rc == 1


class TestCgmlstPerSampleDispatch:
    def test_dispatches_to_ingest_cgmlst(self, fake_env: Path, monkeypatch: pytest.MonkeyPatch):
        called: list[bool] = []

        def fake_ingest(gos):
            called.append(True)
            return ["oid-sample-1"]

        monkeypatch.setattr(ingest_results, "ingest_cgmlst", fake_ingest)
        _patch_argv(monkeypatch, "--cgmlst")

        rc = ingest_results.main()
        assert rc == 0
        assert called == [True]


class TestAllUmbrella:
    """--all covers mainline per-sample ingest AND cgMLST per-sample ingest."""

    def test_all_calls_both_ingest_sample_and_ingest_cgmlst(
        self, fake_env: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ingest_sample_calls: list[str] = []
        ingest_cgmlst_calls: list[bool] = []

        def fake_ingest_sample(gos, sample_id):
            ingest_sample_calls.append(sample_id)
            return f"oid-{sample_id}"

        def fake_ingest_cgmlst(gos):
            ingest_cgmlst_calls.append(True)
            return ["oid-cgmlst-1", "oid-cgmlst-2"]

        monkeypatch.setattr(ingest_results, "ingest_sample", fake_ingest_sample)
        monkeypatch.setattr(ingest_results, "ingest_cgmlst", fake_ingest_cgmlst)
        _patch_argv(monkeypatch, "--all")

        rc = ingest_results.main()
        assert rc == 0
        assert sorted(ingest_sample_calls) == ["SAM-SAL-001", "SAM-SAL-002"]
        assert ingest_cgmlst_calls == [True]


class TestMutualExclusivity:
    def test_cgmlst_and_cgmlst_cohort_rejected(
        self,
        fake_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        _patch_argv(monkeypatch, "--cgmlst", "--cgmlst-cohort")
        with pytest.raises(SystemExit):
            ingest_results.main()
        assert "not allowed with argument" in capsys.readouterr().err

    def test_cgmlst_cohort_and_snp_rejected(
        self,
        fake_env: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        _patch_argv(monkeypatch, "--cgmlst-cohort", "--snp")
        with pytest.raises(SystemExit):
            ingest_results.main()
        assert "not allowed with argument" in capsys.readouterr().err
