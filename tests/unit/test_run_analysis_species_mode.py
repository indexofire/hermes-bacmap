"""--species-mode CLI plumbing (species-id P0)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import run_analysis  # noqa: E402

VALID_MODES = ["simple", "panel", "skani_gtdb", "mash_refseq", "sourmash", "standard"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    wf = tmp_path / "wf"
    (wf / "config").mkdir(parents=True)
    (wf / "config" / "samples.tsv").write_text(
        "sample\tspecies\tR1\tR2\nS1\tSalmonella\tr1.fq\tr2.fq\n"
    )
    monkeypatch.setattr(run_analysis, "ROOT", tmp_path)
    monkeypatch.setattr(run_analysis, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(run_analysis, "RESULTS_DIR", tmp_path / "results")
    captured = {}

    def fake_run(targets, cores=8, timeout=7200, config_overrides=None):
        captured["targets"] = targets
        captured["config_overrides"] = config_overrides
        return True

    monkeypatch.setattr(run_analysis, "run_snakemake", fake_run)
    return captured


class TestSpeciesModeArg:
    def test_valid_mode_passed_to_snakemake(self, env, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["run_analysis", "--sample", "S1", "--species-mode", "sourmash"]
        )
        assert run_analysis.main() == 0
        assert env["config_overrides"] == {"species_mode": "sourmash"}

    def test_default_is_none(self, env, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["run_analysis", "--sample", "S1"])
        assert run_analysis.main() == 0
        assert not env.get("config_overrides")

    def test_invalid_mode_rejected(self, env, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "argv", ["run_analysis", "--sample", "S1", "--species-mode", "psychic"]
        )
        with pytest.raises(SystemExit):
            run_analysis.main()
        assert "invalid choice" in capsys.readouterr().err.lower()

    @pytest.mark.parametrize("mode", VALID_MODES)
    def test_all_enum_values_accepted(self, env, monkeypatch, mode):
        monkeypatch.setattr(sys, "argv", ["run_analysis", "--sample", "S1", "--species-mode", mode])
        assert run_analysis.main() == 0
        assert env["config_overrides"] == {"species_mode": mode}
