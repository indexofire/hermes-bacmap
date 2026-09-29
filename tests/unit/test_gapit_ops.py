"""Unit tests for capability-evolution curation (services/gapit_ops.py).

gapit db build subprocess mocked at module boundary; binary resolution via
config.which (pixi-aware). The wrapper builds custom screening databases
into the gapit datadir and verifies the resulting directory.
"""
from __future__ import annotations

import sys
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.services.gapit_ops import db_build  # noqa: E402

_MOD = "hermes_bacmap.services.gapit_ops"


def _proc(stdout: str = "", stderr: str = "", returncode: int = 0) -> CompletedProcess:
    return CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestDbBuild:
    def test_builds_database_and_returns_path(self, tmp_path):
        fasta = tmp_path / "marker.fa"
        fasta.write_text(">outbreak_marker\nATGC\n")

        def fake_run(cmd, **kwargs):
            name = cmd[cmd.index("build") + 1]
            (tmp_path / "datadir" / name).mkdir(parents=True, exist_ok=True)
            return _proc(stdout="4 records written\n")

        with patch(f"{_MOD}.which", return_value="/fake/gapit"), patch(
            f"{_MOD}.subprocess.run", side_effect=fake_run
        ) as run:
            result = db_build(
                "outbreak_marker",
                fasta,
                datadir=tmp_path / "datadir",
                description="outbreak marker 2026-09",
            )

        assert result["db_name"] == "outbreak_marker"
        assert Path(result["db_path"]).exists()
        assert result["records"] == 4
        cmd = run.call_args.args[0]
        assert cmd[:3] == ["/fake/gapit", "db", "build"]
        assert "outbreak_marker" in cmd
        assert "--description" in cmd

    def test_force_flag_forwarded(self, tmp_path):
        fasta = tmp_path / "m.fa"
        fasta.write_text(">x\nAT\n")

        with patch(f"{_MOD}.which", return_value="/fake/gapit"), patch(
            f"{_MOD}.subprocess.run", return_value=_proc()
        ) as run:
            db_build("m", fasta, datadir=tmp_path, force=True)

        assert "--force" in run.call_args.args[0]

    def test_missing_binary_raises_with_hint(self, tmp_path):
        fasta = tmp_path / "m.fa"
        fasta.write_text(">x\nAT\n")

        with patch(f"{_MOD}.which", return_value=None):
            with pytest.raises(RuntimeError, match="gapit not found"):
                db_build("m", fasta, datadir=tmp_path)

    def test_missing_fasta_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            db_build("m", tmp_path / "nope.fa", datadir=tmp_path)

    def test_nonzero_exit_raises(self, tmp_path):
        fasta = tmp_path / "m.fa"
        fasta.write_text(">x\nAT\n")

        with patch(f"{_MOD}.which", return_value="/fake/gapit"), patch(
            f"{_MOD}.subprocess.run", return_value=_proc(stderr="bad fasta", returncode=1)
        ):
            with pytest.raises(RuntimeError, match="bad fasta"):
                db_build("m", fasta, datadir=tmp_path)

    def test_dbtype_forwarded(self, tmp_path):
        fasta = tmp_path / "m.faa"
        fasta.write_text(">x\nMKV\n")

        with patch(f"{_MOD}.which", return_value="/fake/gapit"), patch(
            f"{_MOD}.subprocess.run", return_value=_proc()
        ) as run:
            db_build("m", fasta, datadir=tmp_path, dbtype="prot")

        cmd = run.call_args.args[0]
        assert cmd[cmd.index("--dbtype") + 1] == "prot"
