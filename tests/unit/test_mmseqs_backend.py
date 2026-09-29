"""Unit tests for the mmseqs2 engine backend.

mmseqs binary and subprocess.run are mocked at the module boundary;
`which` is mocked per-backend-module (backends import it from ``.._env``).
"""
from __future__ import annotations

import sys
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.engine.backends.mmseqs2 import Mmseqs2Backend, parse_cluster_tsv  # noqa: E402

_MOD = "hermes_bacmap.engine.backends.mmseqs2"

# easy-linclust cluster TSV: representative \t member
CLUSTER_TSV = (
    "SAM1__cds001\tSAM1__cds001\n"
    "SAM1__cds001\tSAM2__cds005\n"
    "SAM1__cds001\tSAM3__cds002\n"
    "SAM2__cds010\tSAM2__cds010\n"
    "SAM3__cds007\tSAM3__cds007\n"
    "SAM3__cds007\tSAM1__cds020\n"
)


def _proc(stdout: str = "", stderr: str = "", returncode: int = 0) -> CompletedProcess:
    return CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestInit:
    def test_init_succeeds_when_binary_found(self):
        with patch(f"{_MOD}.which", return_value="/fake/bin/mmseqs"):
            backend = Mmseqs2Backend(threads=2)
        assert backend._bin == "/fake/bin/mmseqs"
        assert backend._threads == 2

    def test_init_raises_when_binary_missing(self):
        with patch(f"{_MOD}.which", return_value=None):
            with pytest.raises(RuntimeError, match="mmseqs not found"):
                Mmseqs2Backend()


class TestCluster:
    def test_cluster_builds_easy_linclust_command(self, tmp_path):
        fasta = tmp_path / "proteins.faa"
        fasta.write_text(">a\nMKVL\n")
        prefix = tmp_path / "clusters"

        with patch(f"{_MOD}.which", return_value="/fake/bin/mmseqs"), patch(
            f"{_MOD}.subprocess.run", return_value=_proc()
        ) as run, patch("pathlib.Path.exists", return_value=True):
            backend = Mmseqs2Backend()
            tsv = backend.cluster(fasta, prefix, min_seq_id=0.9, coverage=0.8)

        assert tsv == tmp_path / "clusters_cluster.tsv"
        cmd = run.call_args.args[0]
        assert cmd[0] == "/fake/bin/mmseqs"
        assert cmd[1] == "easy-linclust"
        assert str(fasta) in cmd
        assert str(prefix) in cmd
        assert "--min-seq-id" in cmd
        assert cmd[cmd.index("--min-seq-id") + 1] == "0.9"
        assert "-c" in cmd
        assert cmd[cmd.index("-c") + 1] == "0.8"
        assert "--threads" in cmd

    def test_cluster_raises_when_output_missing(self, tmp_path):
        fasta = tmp_path / "proteins.faa"
        fasta.write_text(">a\nMKVL\n")
        prefix = tmp_path / "clusters"

        with patch(f"{_MOD}.which", return_value="/fake/bin/mmseqs"), patch(
            f"{_MOD}.subprocess.run", return_value=_proc()
        ):
            backend = Mmseqs2Backend()
            with pytest.raises(RuntimeError, match="did not produce"):
                backend.cluster(fasta, prefix)

    def test_cluster_raises_on_nonzero_exit(self, tmp_path):
        fasta = tmp_path / "proteins.faa"
        fasta.write_text(">a\nMKVL\n")
        prefix = tmp_path / "clusters"

        with patch(f"{_MOD}.which", return_value="/fake/bin/mmseqs"), patch(
            f"{_MOD}.subprocess.run", return_value=_proc(stderr="boom", returncode=1)
        ):
            backend = Mmseqs2Backend()
            with pytest.raises(RuntimeError, match="mmseqs easy-linclust failed: boom"):
                backend.cluster(fasta, prefix)


class TestParseClusterTsv:
    def test_parse_groups_members_by_representative(self, tmp_path):
        tsv = tmp_path / "clusters_cluster.tsv"
        tsv.write_text(CLUSTER_TSV)

        clusters = parse_cluster_tsv(tsv)

        assert set(clusters) == {"SAM1__cds001", "SAM2__cds010", "SAM3__cds007"}
        assert clusters["SAM1__cds001"] == ["SAM1__cds001", "SAM2__cds005", "SAM3__cds002"]
        assert clusters["SAM3__cds007"] == ["SAM3__cds007", "SAM1__cds020"]

    def test_parse_skips_malformed_lines(self, tmp_path):
        tsv = tmp_path / "clusters_cluster.tsv"
        tsv.write_text("rep_only\nrep\tmember\n")

        clusters = parse_cluster_tsv(tsv)

        assert clusters == {"rep": ["member"]}
