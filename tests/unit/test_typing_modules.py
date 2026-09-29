"""TDD tests for Phase 2 typing modules: V. cholerae, L. monocytogenes, C. difficile, B. cereus."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.analysis.gene_scanner import GeneHit, ScanResult  # noqa: E402


def _scan_result(genes: list[tuple[str, float, float]]) -> ScanResult:
    sr = ScanResult(
        database="markers_v2", input_file="/tmp/ctgs.fasta",
        min_identity=85.0, min_coverage=30.0,
    )
    for gene, identity, coverage in genes:
        sr.genes.append(
            GeneHit(gene=gene, identity=identity, coverage=coverage,
                    contig="ctg1", start=1, end=100, strand="+")
        )
    sr.total_hits = len(sr.genes)
    sr.build_summary()
    return sr


class TestVCholeraeGenotype:
    def test_toxigenic(self, monkeypatch):
        from hermes_bacmap.typing import vcholerae_genotype as vc

        monkeypatch.setattr(vc, "scan",
            lambda *a, **kw: _scan_result([("ompW", 99.0, 100.0), ("ctxA", 98.0, 95.0)]))
        r = vc.genotype("/tmp/ctgs.fasta")
        assert r.species == "Vibrio cholerae"
        assert r.toxigenic is True
        assert r.ctxa_positive is True
        assert r.confidence == "high"

    def test_non_toxigenic(self, monkeypatch):
        from hermes_bacmap.typing import vcholerae_genotype as vc

        monkeypatch.setattr(vc, "scan",
            lambda *a, **kw: _scan_result([("ompW", 99.0, 100.0)]))
        r = vc.genotype("/tmp/ctgs.fasta")
        assert r.species == "Vibrio cholerae"
        assert r.toxigenic is False
        assert r.confidence == "medium"

    def test_negative(self, monkeypatch):
        from hermes_bacmap.typing import vcholerae_genotype as vc

        monkeypatch.setattr(vc, "scan", lambda *a, **kw: _scan_result([]))
        r = vc.genotype("/tmp/ctgs.fasta")
        assert r.species == "Unknown"


class TestLMonoSerogroup:
    def _run(self, monkeypatch, genes):
        from hermes_bacmap.typing import lmono_serogroup as ls

        monkeypatch.setattr(ls, "scan",
            lambda *a, **kw: _scan_result(genes))
        return ls.serogroup("/tmp/ctgs.fasta")

    def test_serogroup_1_2a(self, monkeypatch):
        r = self._run(monkeypatch, [("Prs", 99.0, 100.0), ("lmo0737", 98.0, 95.0)])
        assert r.species == "Listeria monocytogenes"
        assert r.serogroup == "1/2a"

    def test_serogroup_1_2b(self, monkeypatch):
        r = self._run(monkeypatch, [("Prs", 99.0, 100.0), ("ORF2819", 98.0, 95.0), ("lmo0737", 97.0, 90.0)])
        assert r.serogroup == "1/2b"

    def test_serogroup_1_2c(self, monkeypatch):
        r = self._run(monkeypatch, [("Prs", 99.0, 100.0), ("lmo1118", 98.0, 95.0), ("ORF2110", 97.0, 90.0)])
        assert r.serogroup == "1/2c"

    def test_serogroup_4b(self, monkeypatch):
        r = self._run(monkeypatch, [("Prs", 99.0, 100.0), ("ORF2110", 98.0, 95.0), ("ORF2819", 97.0, 90.0)])
        assert r.serogroup == "4b"

    def test_not_listeria(self, monkeypatch):
        r = self._run(monkeypatch, [("hly", 99.0, 100.0)])
        assert r.species == "Unknown"
        assert "Prs" in r.interpretation


class TestCdiffToxin:
    def _run(self, monkeypatch, genes):
        from hermes_bacmap.typing import cdiff_toxin as ct

        monkeypatch.setattr(ct, "scan",
            lambda *a, **kw: _scan_result(genes))
        return ct.toxin_type("/tmp/ctgs.fasta")

    def test_toxigenic_classic(self, monkeypatch):
        r = self._run(monkeypatch, [("tcdA", 99.0, 100.0), ("tcdB", 98.0, 95.0)])
        assert r.toxigenic is True
        assert r.toxinotype == "toxigenic (tcdA+ tcdB+)"

    def test_rt027(self, monkeypatch):
        r = self._run(monkeypatch, [
            ("tcdA", 99.0, 100.0), ("tcdB", 98.0, 95.0),
            ("cdtA", 97.0, 90.0), ("cdtB", 96.0, 90.0),
        ])
        assert r.toxigenic is True
        assert r.possible_rt027 is True
        assert r.binary_toxin is True

    def test_non_toxigenic(self, monkeypatch):
        r = self._run(monkeypatch, [])
        assert r.toxigenic is False
        assert r.toxinotype == "non-toxigenic"

    def test_tcdB_only(self, monkeypatch):
        r = self._run(monkeypatch, [("tcdB", 98.0, 95.0)])
        assert r.toxigenic is True
        assert r.confidence == "medium"


class TestBcereusToxin:
    def _run(self, monkeypatch, genes):
        from hermes_bacmap.typing import bcereus_toxin as bt

        monkeypatch.setattr(bt, "scan",
            lambda *a, **kw: _scan_result(genes))
        return bt.toxin_type("/tmp/ctgs.fasta")

    def test_diarrheal(self, monkeypatch):
        r = self._run(monkeypatch, [("nheB", 99.0, 100.0)])
        assert r.toxin_type == "diarrheal"

    def test_emetic(self, monkeypatch):
        r = self._run(monkeypatch, [("ces", 98.0, 95.0)])
        assert r.toxin_type == "emetic"

    def test_negative(self, monkeypatch):
        r = self._run(monkeypatch, [])
        assert r.toxin_type == "non-toxigenic"
