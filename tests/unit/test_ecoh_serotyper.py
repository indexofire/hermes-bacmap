"""Tests for hermes_bacmap.typing.ecoh_serotyper — O:H antigen parsing logic."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.analysis.gene_scanner import GeneHit, ScanResult  # noqa: E402
from hermes_bacmap.typing import ecoh_serotyper  # noqa: E402


def _hit(gene: str, identity: float, coverage: float, contig: str = "ctg1") -> GeneHit:
    return GeneHit(
        gene=gene,
        identity=identity,
        coverage=coverage,
        contig=contig,
        start=1,
        end=100,
        strand="+",
    )


def _scan(*genes: GeneHit, db_name: str = "ecoh") -> ScanResult:
    sr = ScanResult(
        database=db_name,
        input_file="dummy.fasta",
        min_identity=80.0,
        min_coverage=80.0,
        genes=list(genes),
    )
    sr.total_hits = len(genes)
    sr.unique_genes = sorted({g.gene for g in genes})
    return sr


class TestParseAntigen:
    def test_wzx_o(self):
        assert ecoh_serotyper._parse_antigen("wzx-O157") == ("wzx", "O", "157")

    def test_wzy_o(self):
        assert ecoh_serotyper._parse_antigen("wzy-O26") == ("wzy", "O", "26")

    def test_wzm_o(self):
        assert ecoh_serotyper._parse_antigen("wzm-O111") == ("wzm", "O", "111")

    def test_wzt_o(self):
        assert ecoh_serotyper._parse_antigen("wzt-O8") == ("wzt", "O", "8")

    def test_flic_h(self):
        assert ecoh_serotyper._parse_antigen("fliC-H7") == ("fliC", "H", "7")

    def test_flka_h(self):
        assert ecoh_serotyper._parse_antigen("flkA-H11") == ("flkA", "H", "11")

    def test_flla_h(self):
        assert ecoh_serotyper._parse_antigen("fllA-H21") == ("fllA", "H", "21")

    def test_flma_h(self):
        assert ecoh_serotyper._parse_antigen("flmA-H19") == ("flmA", "H", "19")

    def test_flna_h(self):
        assert ecoh_serotyper._parse_antigen("flnA-H12") == ("flnA", "H", "12")

    def test_unknown_gene_returns_none(self):
        assert ecoh_serotyper._parse_antigen("stx1") is None

    def test_o_pattern_strips_gp_suffix(self):
        assert ecoh_serotyper._parse_antigen("wzx-O45Gp") == ("wzx", "O", "45")

    def test_h_pattern_strips_gp_suffix(self):
        assert ecoh_serotyper._parse_antigen("fliC-H8Gp") == ("fliC", "H", "8")

    def test_o_pattern_splits_dash_in_value(self):
        # regex matches up to whitespace, then split('-')[0] takes the head
        assert ecoh_serotyper._parse_antigen("wzx-O157-variant") == ("wzx", "O", "157")


class TestSerotypeDecision:
    def test_clear_o_and_h(self, monkeypatch):
        scan_in = _scan(
            _hit("wzx-O157", 99.0, 100.0),
            _hit("wzy-O157", 98.0, 99.0),
            _hit("fliC-H7", 99.5, 100.0),
        )
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        assert r.o_type == "157"
        assert r.h_type == "7"
        assert r.serotype == "O157:H7"

    def test_o_only(self, monkeypatch):
        scan_in = _scan(_hit("wzx-O26", 99.0, 95.0))
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        assert r.o_type == "26"
        assert r.h_type == "-"
        assert r.serotype == "O26:H-"

    def test_h_only(self, monkeypatch):
        scan_in = _scan(_hit("fliC-H7", 95.0, 90.0))
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        assert r.o_type == "-"
        assert r.h_type == "7"
        assert r.serotype == "O-:H7"

    def test_no_hits_undetermined(self, monkeypatch):
        scan_in = _scan()
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        assert r.o_type == "-"
        assert r.h_type == "-"
        assert r.serotype == "-:-"

    def test_unknown_gene_ignored(self, monkeypatch):
        scan_in = _scan(
            _hit("stx2", 99.0, 100.0),
            _hit("uidA", 100.0, 100.0),
            _hit("wzx-O111", 95.0, 95.0),
        )
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        assert r.o_type == "111"
        assert r.h_type == "-"
        assert len(r.o_hits) == 1
        assert len(r.h_hits) == 0

    def test_best_score_wins_for_duplicate_antigen_group(self, monkeypatch):
        scan_in = _scan(
            _hit("wzx-O157", 90.0, 90.0),
            _hit("wzy-O157", 99.0, 99.0),
        )
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        assert r.o_type == "157"
        assert len(r.o_hits) == 2

    def test_two_o_groups_picks_higher_score(self, monkeypatch):
        scan_in = _scan(
            _hit("wzx-O26", 90.0, 90.0),
            _hit("wzx-O157", 100.0, 100.0),
        )
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        assert r.o_type == "157"

    def test_two_h_groups_picks_higher_score(self, monkeypatch):
        scan_in = _scan(
            _hit("fliC-H7", 80.0, 80.0),
            _hit("fliC-H4", 99.0, 99.0),
        )
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        assert r.h_type == "4"

    def test_kwargs_forwarded_to_scan(self, monkeypatch):
        captured = {}

        def fake_scan(fasta, **kw):
            captured.update(kw)
            return _scan()

        monkeypatch.setattr(ecoh_serotyper, "scan", fake_scan)
        ecoh_serotyper.serotype("/fake.fasta", min_identity=90.0, threads=8)
        assert captured["min_identity"] == 90.0
        assert captured["threads"] == 8


class TestSerotypeResultAndSorting:
    def test_hits_sorted_by_identity_desc(self, monkeypatch):
        scan_in = _scan(
            _hit("wzx-O1", 80.0, 100.0),
            _hit("wzy-O1", 99.0, 100.0),
            _hit("fliC-H7", 90.0, 100.0),
        )
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        ids = [h["identity"] for h in r.o_hits]
        assert ids == sorted(ids, reverse=True)

    def test_to_dict_keys(self, monkeypatch):
        scan_in = _scan(_hit("wzx-O157", 99.0, 100.0), _hit("fliC-H7", 99.0, 100.0))
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        d = r.to_dict()
        assert set(d.keys()) == {
            "o_type",
            "h_type",
            "serotype",
            "o_antigen_hits",
            "h_antigen_hits",
            "interpretation",
        }

    def test_interpretation_text_present_when_hit(self, monkeypatch):
        scan_in = _scan(_hit("wzx-O157", 99.0, 100.0), _hit("fliC-H7", 99.0, 100.0))
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        interp = r.to_dict()["interpretation"]
        assert "O antigen: O157" in interp
        assert "H antigen: H7" in interp
        assert "Serotype: O157:H7" in interp

    def test_interpretation_text_when_no_hits(self, monkeypatch):
        scan_in = _scan()
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        r = ecoh_serotyper.serotype("/fake/contigs.fasta")
        interp = r.to_dict()["interpretation"]
        assert "No O antigen detected" in interp
        assert "No H antigen" in interp


class TestEcohMainCli:
    def test_main_text_output(self, monkeypatch, capsys):
        scan_in = _scan(
            _hit("wzx-O157", 99.0, 100.0),
            _hit("fliC-H7", 99.0, 100.0),
        )
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        monkeypatch.setattr(sys, "argv", ["ecoh_serotyper", "/fake/contigs.fasta"])

        ecoh_serotyper.main()
        out = capsys.readouterr().out
        assert "O157:H7" in out
        assert "O hits" in out

    def test_main_json_output(self, monkeypatch, capsys):
        scan_in = _scan(_hit("wzx-O26", 99.0, 95.0))
        monkeypatch.setattr(ecoh_serotyper, "scan", lambda *a, **k: scan_in)
        monkeypatch.setattr(sys, "argv", ["ecoh_serotyper", "/fake/contigs.fasta", "--json"])

        ecoh_serotyper.main()
        out = capsys.readouterr().out
        import json

        parsed = json.loads(out)
        assert parsed["o_type"] == "26"
        assert parsed["h_type"] == "-"
