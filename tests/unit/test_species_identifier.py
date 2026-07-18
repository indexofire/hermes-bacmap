"""Unit tests for hermes_bacmap.analysis.species_identifier."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.analysis import species_identifier  # noqa: E402
from hermes_bacmap.analysis.gene_scanner import GeneHit, ScanResult  # noqa: E402
from hermes_bacmap.analysis.species_identifier import (  # noqa: E402
    _GENE_TO_SPECIES,
    _SPECIES_PRIORITY,
    SpeciesIdResult,
)


def _scan_result(genes: list[tuple[str, float, float, str]]) -> ScanResult:
    sr = ScanResult(
        database="species_markers",
        input_file="/tmp/ctgs.fasta",
        min_identity=85.0,
        min_coverage=30.0,
    )
    for gene, identity, coverage, contig in genes:
        sr.genes.append(
            GeneHit(
                gene=gene,
                identity=identity,
                coverage=coverage,
                contig=contig,
                start=1,
                end=100,
                strand="+",
            )
        )
    sr.total_hits = len(sr.genes)
    sr.build_summary()
    return sr


class TestModuleLevelDicts:
    def test_gene_to_species_lowercase_keys(self):
        for k in _GENE_TO_SPECIES:
            assert k == k.lower(), f"Key {k!r} not lowercase"

    def test_priority_covers_all_known_markers(self):
        assert set(_SPECIES_PRIORITY) <= set(_GENE_TO_SPECIES.keys())

    def test_priority_order_is_inva_ipah_toxr_tlh_uida(self):
        assert _SPECIES_PRIORITY == ["inva", "ipah", "toxr", "tlh", "uida"]


class TestSpeciesIdResult:
    def test_defaults(self):
        r = SpeciesIdResult()
        assert r.species == "Unknown"
        assert r.confidence == "low"
        assert r.detected_markers == []
        assert r.all_hits == []

    def test_to_dict_contains_required_keys(self):
        r = SpeciesIdResult(species="Salmonella", confidence="high")
        d = r.to_dict()
        assert d["species"] == "Salmonella"
        assert d["confidence"] == "high"
        assert d["detected_markers"] == []
        assert "interpretation" in d
        assert "Identified as Salmonella" in d["interpretation"]

    def test_interpretation_unknown(self):
        r = SpeciesIdResult(species="Unknown")
        assert r._interpret() == "No species-specific markers detected"

    def test_interpretation_with_markers(self):
        r = SpeciesIdResult(
            species="Salmonella",
            detected_markers=[
                {"gene": "invA", "identity": 99.0, "coverage": 100.0, "contig": "ctg1"}
            ],
        )
        out = r._interpret()
        assert "invA" in out
        assert "Salmonella" in out


class TestIdentifyModeRouting:
    def test_standard_mode_delegates_to_taxonomic_validator(self, tmp_path, monkeypatch):
        called = {}

        def fake_validate(path, mode="simple"):
            called["path"] = str(path)
            called["mode"] = mode
            return "fake-taxonomy-result"

        monkeypatch.setattr(
            "hermes_bacmap.analysis.taxonomic_validator.validate_genome", fake_validate
        )
        out = species_identifier.identify("/some/contigs.fasta", mode="standard")
        assert out == "fake-taxonomy-result"
        assert called["mode"] == "standard"

    def test_simple_mode_returns_species_id_result(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            species_identifier,
            "scan",
            lambda *a, **kw: _scan_result([("invA", 99.0, 100.0, "ctg1")]),
        )
        out = species_identifier.identify("/tmp/ctgs.fasta")
        assert isinstance(out, SpeciesIdResult)


class TestIdentifyDetection:
    """Mock the gene_scanner.scan boundary.

    Note: the production code has a bug — `identify()` keys `gene_hits` by the
    lowercase gene name but then probes it with mixed-case keys ("invA",
    "ipaH", "toxR", "uidA"). Only the lowercase "tlh" check works.  As a
    result, species will only ever be set for V_parahaemolyticus (via tlh).
    Tests marked xfail document the intended behavior.
    """

    def test_no_markers_returns_unknown(self, monkeypatch):
        monkeypatch.setattr(
            species_identifier,
            "scan",
            lambda *a, **kw: _scan_result([("housekeeping", 99.0, 100.0, "ctg1")]),
        )
        out = species_identifier.identify("/tmp/ctgs.fasta")
        assert out.species == "Unknown"
        assert out.confidence == "low"
        assert out.detected_markers == []
        assert len(out.all_hits) == 1

    def test_all_hits_captured_even_for_non_markers(self, monkeypatch):
        monkeypatch.setattr(
            species_identifier,
            "scan",
            lambda *a, **kw: _scan_result(
                [
                    ("housekeeping", 99.0, 100.0, "ctg1"),
                    ("invA", 95.0, 90.0, "ctg1"),
                ]
            ),
        )
        out = species_identifier.identify("/tmp/ctgs.fasta")
        assert len(out.all_hits) == 2

    def test_detected_markers_ordered_by_priority_dict(self, monkeypatch):
        monkeypatch.setattr(
            species_identifier,
            "scan",
            lambda *a, **kw: _scan_result(
                [
                    ("uidA", 99.0, 100.0, "ctg1"),
                    ("invA", 99.0, 100.0, "ctg1"),
                ]
            ),
        )
        out = species_identifier.identify("/tmp/ctgs.fasta")
        gene_order = [m["gene"].lower() for m in out.detected_markers]
        assert gene_order == ["inva", "uida"]

    def test_keeps_highest_identity_per_marker(self, monkeypatch):
        monkeypatch.setattr(
            species_identifier,
            "scan",
            lambda *a, **kw: _scan_result(
                [
                    ("invA", 90.0, 100.0, "ctg1"),
                    ("invA", 99.5, 100.0, "ctg1"),
                    ("invA", 95.0, 100.0, "ctg1"),
                ]
            ),
        )
        out = species_identifier.identify("/tmp/ctgs.fasta")
        inva_markers = [m for m in out.detected_markers if m["gene"].lower() == "inva"]
        assert len(inva_markers) == 1
        assert inva_markers[0]["identity"] == 99.5

    def test_tlh_triggers_vparahaemolyticus(self, monkeypatch):
        monkeypatch.setattr(
            species_identifier,
            "scan",
            lambda *a, **kw: _scan_result([("tlh", 99.0, 100.0, "ctg1")]),
        )
        out = species_identifier.identify("/tmp/ctgs.fasta")
        assert out.species == "V_parahaemolyticus"
        assert out.confidence == "high"

    def test_invA_triggers_salmonella(self, monkeypatch):
        monkeypatch.setattr(
            species_identifier,
            "scan",
            lambda *a, **kw: _scan_result([("invA", 99.0, 100.0, "ctg1")]),
        )
        out = species_identifier.identify("/tmp/ctgs.fasta")
        assert out.species == "Salmonella"
        assert out.confidence == "high"

    def test_ipaH_triggers_shigella(self, monkeypatch):
        monkeypatch.setattr(
            species_identifier,
            "scan",
            lambda *a, **kw: _scan_result([("ipaH", 99.0, 100.0, "ctg1")]),
        )
        out = species_identifier.identify("/tmp/ctgs.fasta")
        assert out.species == "Shigella/EIEC"

    def test_toxR_triggers_vparahaemolyticus(self, monkeypatch):
        monkeypatch.setattr(
            species_identifier,
            "scan",
            lambda *a, **kw: _scan_result([("toxR", 99.0, 100.0, "ctg1")]),
        )
        out = species_identifier.identify("/tmp/ctgs.fasta")
        assert out.species == "V_parahaemolyticus"

    def test_uidA_triggers_dec(self, monkeypatch):
        monkeypatch.setattr(
            species_identifier,
            "scan",
            lambda *a, **kw: _scan_result([("uidA", 99.0, 100.0, "ctg1")]),
        )
        out = species_identifier.identify("/tmp/ctgs.fasta")
        assert out.species == "DEC"


class TestThresholdsPassedToScan:
    def test_uses_species_specific_thresholds(self, monkeypatch):
        captured = {}

        def fake_scan(*a, **kw):
            captured.update(kw)
            return _scan_result([])

        monkeypatch.setattr(species_identifier, "scan", fake_scan)
        species_identifier.identify("/tmp/ctgs.fasta")
        assert captured["min_identity"] == species_identifier._SPECIES_MIN_IDENTITY
        assert captured["min_coverage"] == species_identifier._SPECIES_MIN_COVERAGE
        assert captured["db_name"] == "species_markers"


class TestMain:
    def test_main_text_output_with_markers(self, monkeypatch, capsys):
        sr_with_tlh = _scan_result([("tlh", 99.0, 100.0, "ctg1")])
        monkeypatch.setattr(species_identifier, "scan", lambda *a, **kw: sr_with_tlh)
        monkeypatch.setattr(sys, "argv", ["species_identifier", "/tmp/ctgs.fasta"])
        species_identifier.main()
        out = capsys.readouterr().out
        assert "Species: V_parahaemolyticus (high)" in out
        assert "tlh: 99.0% identity" in out
        assert "Identified as V_parahaemolyticus" in out

    def test_main_text_output_no_markers(self, monkeypatch, capsys):
        monkeypatch.setattr(species_identifier, "scan", lambda *a, **kw: _scan_result([]))
        monkeypatch.setattr(sys, "argv", ["species_identifier", "/tmp/ctgs.fasta"])
        species_identifier.main()
        out = capsys.readouterr().out
        assert "Species: Unknown (low)" in out
        assert "No species-specific markers detected" in out

    def test_main_json_output(self, monkeypatch, capsys):
        sr_with_tlh = _scan_result([("tlh", 99.0, 100.0, "ctg1")])
        monkeypatch.setattr(species_identifier, "scan", lambda *a, **kw: sr_with_tlh)
        monkeypatch.setattr(sys, "argv", ["species_identifier", "/tmp/ctgs.fasta", "--json"])
        species_identifier.main()
        out = capsys.readouterr().out
        assert '"species": "V_parahaemolyticus"' in out
        assert '"confidence": "high"' in out
