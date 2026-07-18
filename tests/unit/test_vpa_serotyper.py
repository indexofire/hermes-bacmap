"""Tests for hermes_bacmap.typing.vpa_serotyper — VpaSerotyper wrapper."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.typing import vpa_serotyper as vs  # noqa: E402


class _FakeEngine:
    def __init__(self, payload: dict, raise_exc: Exception | None = None) -> None:
        self._payload = payload
        self._raise = raise_exc

    def run_one_sample(self, contigs_path: Path) -> dict:
        if self._raise is not None:
            raise self._raise
        return self._payload


class TestVpaSerotyperHappyPath:
    def test_full_dict_mapping(self, monkeypatch, tmp_path):
        payload = {
            "Sample": "SAM-VPA-001",
            "O_Locus": "OL1",
            "K_Locus": "KL1",
            "O_Confidence": "High",
            "K_Confidence": "Medium",
            "O_Coverage": 99.5,
            "K_Coverage": 88.0,
            "O_Identity": 99.0,
            "K_Identity": 95.0,
            "Predicted_Serotype": "O1:K1",
            "O_Missing_Genes": "None",
            "K_Missing_Genes": "wzz",
            "O_Alerts": "None",
            "K_Alerts": "Fragmented",
        }
        fake_engine = _FakeEngine(payload)
        monkeypatch.setattr(vs, "SerotyperEngine", lambda db_dir: fake_engine)

        serotyper = vs.VpaSerotyper(db_dir=tmp_path)
        result = serotyper.analyze("/fake/contigs.fasta", sample_id="SAM-VPA-001")
        assert result.sample == "SAM-VPA-001"
        assert result.o_locus == "OL1"
        assert result.k_locus == "KL1"
        assert result.o_confidence == "High"
        assert result.k_confidence == "Medium"
        assert result.o_coverage == 99.5
        assert result.k_coverage == 88.0
        assert result.o_identity == 99.0
        assert result.k_identity == 95.0
        assert result.predicted_serotype == "O1:K1"
        assert result.o_missing_genes == "None"
        assert result.k_missing_genes == "wzz"
        assert result.o_alerts == "None"
        assert result.k_alerts == "Fragmented"

    def test_sample_id_inferred_from_path_when_missing(self, monkeypatch, tmp_path):
        payload = {"Sample": "ignored"}
        fake_engine = _FakeEngine(payload)
        monkeypatch.setattr(vs, "SerotyperEngine", lambda db_dir: fake_engine)

        serotyper = vs.VpaSerotyper(db_dir=tmp_path)
        result = serotyper.analyze("/data/results/SAM-XYZ/assembly/contigs.fasta")
        assert result.sample == "ignored"

    def test_sample_id_falls_back_to_parent_parent_when_engine_silent(self, monkeypatch, tmp_path):
        payload = {}
        fake_engine = _FakeEngine(payload)
        monkeypatch.setattr(vs, "SerotyperEngine", lambda db_dir: fake_engine)

        serotyper = vs.VpaSerotyper(db_dir=tmp_path)
        result = serotyper.analyze("/data/results/SAM-XYZ/assembly/contigs.fasta")
        assert result.sample == "SAM-XYZ"

    def test_to_dict_round_trip(self, monkeypatch, tmp_path):
        payload = {
            "Sample": "S1",
            "O_Locus": "OL2",
            "K_Locus": "KL3",
            "O_Confidence": "Perfect",
            "K_Confidence": "Low",
            "O_Coverage": 100.0,
            "K_Coverage": 50.0,
            "O_Identity": 100.0,
            "K_Identity": 60.0,
            "Predicted_Serotype": "O2:K3",
        }
        fake_engine = _FakeEngine(payload)
        monkeypatch.setattr(vs, "SerotyperEngine", lambda db_dir: fake_engine)

        serotyper = vs.VpaSerotyper(db_dir=tmp_path)
        result = serotyper.analyze("/fake/contigs.fasta", sample_id="S1")
        d = result.to_dict()
        assert d["sample"] == "S1"
        assert d["o_locus"] == "OL2"
        assert d["k_locus"] == "KL3"
        assert d["predicted_serotype"] == "O2:K3"

    def test_engine_is_cached(self, monkeypatch, tmp_path):
        payload = {"Sample": "S1"}
        fake_engine = _FakeEngine(payload)
        instance_count = {"n": 0}

        def factory(db_dir):
            instance_count["n"] += 1
            return fake_engine

        monkeypatch.setattr(vs, "SerotyperEngine", factory)

        serotyper = vs.VpaSerotyper(db_dir=tmp_path)
        serotyper.analyze("/fake/contigs.fasta", sample_id="S1")
        serotyper.analyze("/fake/contigs.fasta", sample_id="S2")
        assert instance_count["n"] == 1


class TestVpaSerotyperErrorPaths:
    def test_missing_db_dir_raises_file_not_found(self, tmp_path):
        empty = tmp_path / "nonexistent"
        serotyper = vs.VpaSerotyper(db_dir=empty)
        result = serotyper.analyze("/fake/contigs.fasta", sample_id="S1")
        assert result.sample == "S1"
        assert "Error:" in result.o_alerts
        assert "Error:" in result.k_alerts
        assert "VPA serotype DB not found" in result.o_alerts

    def test_generic_exception_returns_error_result(self, monkeypatch, tmp_path):
        fake_engine = _FakeEngine({}, raise_exc=RuntimeError("minimap2 crashed"))
        monkeypatch.setattr(vs, "SerotyperEngine", lambda db_dir: fake_engine)

        serotyper = vs.VpaSerotyper(db_dir=tmp_path)
        result = serotyper.analyze("/fake/contigs.fasta", sample_id="S9")
        assert result.sample == "S9"
        assert "Error: minimap2 crashed" in result.o_alerts
        assert "Error: minimap2 crashed" in result.k_alerts
        assert result.predicted_serotype == "OUT:KUT"
        assert result.o_locus == "None"


class TestVpaSerotyperDefaults:
    def test_default_db_dir_resolves_to_package_data(self):
        s = vs.VpaSerotyper()
        assert s.db_dir.name == "vpa_serotype"
        assert "data" in s.db_dir.parts

    def test_passed_db_dir_wraps_to_path(self, tmp_path):
        s = vs.VpaSerotyper(db_dir=str(tmp_path))
        assert isinstance(s.db_dir, Path)
        assert s.db_dir == tmp_path

    def test_engine_initially_none(self):
        s = vs.VpaSerotyper(db_dir=Path("/tmp"))
        assert s._engine is None


class TestAnalyzeToJson:
    def test_returns_plain_dict(self, monkeypatch, tmp_path):
        payload = {"Sample": "S1", "O_Locus": "OL1"}
        fake_engine = _FakeEngine(payload)
        monkeypatch.setattr(vs, "SerotyperEngine", lambda db_dir: fake_engine)

        serotyper = vs.VpaSerotyper(db_dir=tmp_path)
        d = serotyper.analyze_to_json("/fake/contigs.fasta", sample_id="S1")
        assert isinstance(d, dict)
        assert d["sample"] == "S1"
        assert d["o_locus"] == "OL1"


class TestSerotypeResultDefaults:
    def test_defaults(self):
        r = vs.SerotypeResult()
        assert r.sample == ""
        assert r.o_locus == "None"
        assert r.k_locus == "None"
        assert r.o_confidence == "Unknown"
        assert r.k_confidence == "Unknown"
        assert r.predicted_serotype == "OUT:KUT"
        assert r.o_missing_genes == "None"
        assert r.k_missing_genes == "None"
        assert r.o_alerts == "None"
        assert r.k_alerts == "None"

    def test_to_dict_keys(self):
        r = vs.SerotypeResult()
        d = r.to_dict()
        expected_keys = {
            "sample",
            "predicted_serotype",
            "o_locus",
            "o_confidence",
            "o_coverage",
            "o_identity",
            "o_missing_genes",
            "o_alerts",
            "k_locus",
            "k_confidence",
            "k_coverage",
            "k_identity",
            "k_missing_genes",
            "k_alerts",
        }
        assert set(d.keys()) == expected_keys
