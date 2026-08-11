"""CLI dispatch tests for scripts/run_analysis.py (plan todo 15).

Verifies that --cgmlst and --cgmlst-cohort build the correct snakemake
target lists without actually invoking snakemake. The --snp wiring
(run_analysis.py:217-219) is the template; these tests mirror it for the
two new cgMLST flags and check that --snp still dispatches unchanged
(regression guard).

The strategy: monkeypatch ROOT/WORKFLOW_DIR/RESULTS_DIR/SAMPLES_TSV at a
tmp_path, stub run_snakemake to capture targets, set sys.argv, call
main(), assert captured targets.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import _common  # noqa: E402
import run_analysis  # noqa: E402

# 3 Salmonella + 2 E.coli/Shigella + 1 Vparahaemolyticus.
# salmonella group: 3 samples -> active (>=2)
# ecoli group: 2 samples -> active (>=2)
# vpara group: 1 sample -> inactive (<2)
_SAMPLES_TSV = (
    "sample\tspecies\tR1\tR2\n"
    "SAM-SAL-001\tSalmonella\tr1.fq\tr2.fq\n"
    "SAM-SAL-002\tSalmonella\tr1.fq\tr2.fq\n"
    "SAM-SAL-003\tSalmonella\tr1.fq\tr2.fq\n"
    "SAM-DEC-001\tE.coli\tr1.fq\tr2.fq\n"
    "SAM-SHI-001\tShigella\tr1.fq\tr2.fq\n"
    "SAM-VPA-001\tV.parahaemolyticus\tr1.fq\tr2.fq\n"
)


@pytest.fixture
def fake_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    workflow_dir = tmp_path / "workflows" / "bacmap"
    config_dir = workflow_dir / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "samples.tsv").write_text(_SAMPLES_TSV)

    monkeypatch.setattr(run_analysis, "ROOT", tmp_path)
    monkeypatch.setattr(run_analysis, "WORKFLOW_DIR", workflow_dir)
    monkeypatch.setattr(run_analysis, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(_common, "SAMPLES_TSV", config_dir / "samples.tsv")
    monkeypatch.setattr(_common, "ROOT", tmp_path)
    return tmp_path


def _patch_argv(monkeypatch: pytest.MonkeyPatch, *argv: str) -> None:
    monkeypatch.setattr(sys, "argv", ["run_analysis.py", *argv])


def _capture_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> list[list[str]]:
    captured: list[list[str]] = []

    def fake_run(targets: list[str], cores: int = 8, timeout: int = 7200) -> bool:
        captured.append(list(targets))
        return True

    monkeypatch.setattr(run_analysis, "run_snakemake", fake_run)
    return captured


class TestCgmlstFlag:
    def test_builds_one_target_per_sample(
        self, fake_workflow: Path, monkeypatch: pytest.MonkeyPatch
    ):
        captured = _capture_targets(monkeypatch)
        _patch_argv(monkeypatch, "--cgmlst")

        rc = run_analysis.main()
        assert rc == 0
        assert len(captured) == 1
        targets = captured[0]
        assert len(targets) == 6
        for sample in (
            "SAM-SAL-001",
            "SAM-SAL-002",
            "SAM-SAL-003",
            "SAM-DEC-001",
            "SAM-SHI-001",
            "SAM-VPA-001",
        ):
            expected = str(fake_workflow / "results" / sample / "typing" / "cgmlst.tsv")
            assert expected in targets

    def test_passes_cores_arg(self, fake_workflow: Path, monkeypatch: pytest.MonkeyPatch):
        cores_seen: list[int] = []

        def fake_run(targets: list[str], cores: int = 8, timeout: int = 7200) -> bool:
            cores_seen.append(cores)
            return True

        monkeypatch.setattr(run_analysis, "run_snakemake", fake_run)
        _patch_argv(monkeypatch, "--cgmlst", "--cores", "4")

        rc = run_analysis.main()
        assert rc == 0
        assert cores_seen == [4]


class TestCgmlstCohortFlag:
    def test_targets_only_groups_with_two_plus_samples(
        self, fake_workflow: Path, monkeypatch: pytest.MonkeyPatch
    ):
        captured = _capture_targets(monkeypatch)
        _patch_argv(monkeypatch, "--cgmlst-cohort")

        rc = run_analysis.main()
        assert rc == 0
        assert len(captured) == 1
        targets = captured[0]
        assert len(targets) == 2
        assert (
            str(fake_workflow / "results" / "cgmlst" / "salmonella" / "cgmlst_summary.json")
            in targets
        )
        assert (
            str(fake_workflow / "results" / "cgmlst" / "ecoli" / "cgmlst_summary.json") in targets
        )
        assert (
            str(fake_workflow / "results" / "cgmlst" / "vpara" / "cgmlst_summary.json")
            not in targets
        )

    def test_no_active_groups_yields_empty_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        workflow_dir = tmp_path / "workflows" / "bacmap"
        config_dir = workflow_dir / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "samples.tsv").write_text(
            "sample\tspecies\tR1\tR2\n"
            "SAM-SAL-001\tSalmonella\tr1.fq\tr2.fq\n"
            "SAM-VPA-001\tV.parahaemolyticus\tr1.fq\tr2.fq\n"
        )
        monkeypatch.setattr(run_analysis, "ROOT", tmp_path)
        monkeypatch.setattr(run_analysis, "WORKFLOW_DIR", workflow_dir)
        monkeypatch.setattr(run_analysis, "RESULTS_DIR", tmp_path / "results")
        monkeypatch.setattr(_common, "SAMPLES_TSV", config_dir / "samples.tsv")
        monkeypatch.setattr(_common, "ROOT", tmp_path)

        captured = _capture_targets(monkeypatch)
        _patch_argv(monkeypatch, "--cgmlst-cohort")

        rc = run_analysis.main()
        assert rc == 0
        assert captured == [[]]


class TestSnpRegression:
    """--snp dispatch is unchanged by the new cgMLST flags."""

    def test_snp_target_unchanged(self, fake_workflow: Path, monkeypatch: pytest.MonkeyPatch):
        captured = _capture_targets(monkeypatch)
        _patch_argv(monkeypatch, "--snp")

        rc = run_analysis.main()
        assert rc == 0
        assert captured == [[str(fake_workflow / "results" / "snp" / "snp_summary.json")]]


class TestMutualExclusivity:
    """The two new flags join the same mutually-exclusive group as --snp."""

    def test_cgmlst_and_cgmlst_cohort_rejected(
        self,
        fake_workflow: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        _patch_argv(monkeypatch, "--cgmlst", "--cgmlst-cohort")
        with pytest.raises(SystemExit):
            run_analysis.main()
        assert "not allowed with argument" in capsys.readouterr().err

    def test_cgmlst_and_snp_rejected(
        self,
        fake_workflow: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        _patch_argv(monkeypatch, "--cgmlst", "--snp")
        with pytest.raises(SystemExit):
            run_analysis.main()
        assert "not allowed with argument" in capsys.readouterr().err

    def test_cgmlst_cohort_and_snp_rejected(
        self,
        fake_workflow: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        _patch_argv(monkeypatch, "--cgmlst-cohort", "--snp")
        with pytest.raises(SystemExit):
            run_analysis.main()
        assert "not allowed with argument" in capsys.readouterr().err


class TestValidateAllSampleNamesGuard:
    """The security guard still runs before snakemake for every dispatch."""

    def test_cgmlst_cohort_still_validates_sample_names(
        self,
        fake_workflow: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        validate_calls: list[bool] = []

        def fake_validate() -> list[str]:
            validate_calls.append(True)
            return ["SAM-SAL-001", "SAM-SAL-002", "SAM-SAL-003"]

        monkeypatch.setattr(run_analysis, "validate_all_sample_names", fake_validate)
        _capture_targets(monkeypatch)
        _patch_argv(monkeypatch, "--cgmlst-cohort")

        run_analysis.main()
        assert len(validate_calls) >= 1
