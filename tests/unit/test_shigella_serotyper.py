"""Tests for hermes_bacmap.typing.shigella_serotyper — rule coverage for 58 serotypes."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.analysis.gene_scanner import GeneHit, ScanResult  # noqa: E402
from hermes_bacmap.typing import shigella_serotyper as ss  # noqa: E402


def _scan(unique_genes: list[str]) -> ScanResult:
    sr = ScanResult(
        database="shigella_ref",
        input_file="dummy.fasta",
        min_identity=80.0,
        min_coverage=80.0,
    )
    sr.unique_genes = list(unique_genes)
    sr.genes = [
        GeneHit(gene=g, identity=99.0, coverage=100.0, contig="ctg1", start=1, end=100, strand="+")
        for g in unique_genes
    ]
    sr.total_hits = len(unique_genes)
    return sr


def _serotype(monkeypatch, genes: list[str]) -> ss.ShigellaSerotypeResult:
    scan_in = _scan(genes)
    monkeypatch.setattr(ss, "scan", lambda *a, **k: scan_in)
    return ss.serotype("/fake/contigs.fasta")


class TestDetermineFlexneriType:
    def test_serotype_6(self):
        assert ss._determine_flexneri_type({"Sf6_wzx"}) == (
            "Shigella flexneri serotype 6",
            "high",
        )

    def test_serotype_y_no_gtr(self):
        assert ss._determine_flexneri_type({"Sf_wzx"}) == (
            "Shigella flexneri serotype Y",
            "high",
        )

    def test_serotype_y_via_wzy(self):
        assert ss._determine_flexneri_type({"Sf_wzy"}) == (
            "Shigella flexneri serotype Y",
            "high",
        )

    def test_serotype_1a_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrI"}) == (
            "Shigella flexneri serotype 1a",
            "high",
        )

    def test_serotype_1b_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrI", "Oac1b"}) == (
            "Shigella flexneri serotype 1b",
            "high",
        )

    def test_serotype_1c_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrI", "gtrIC"}) == (
            "Shigella flexneri serotype 1c (7a)",
            "high",
        )

    def test_serotype_7b_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrI", "gtrIC", "Oac1b"}) == (
            "Shigella flexneri serotype 7b",
            "high",
        )

    def test_serotype_2a_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrII"}) == (
            "Shigella flexneri serotype 2a",
            "high",
        )

    def test_serotype_2av_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrII", "Xv"}) == (
            "Shigella flexneri 2av",
            "high",
        )

    def test_serotype_2b_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrII", "gtrX"}) == (
            "Shigella flexneri serotype 2b",
            "high",
        )

    def test_serotype_4a_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrIV"}) == (
            "Shigella flexneri serotype 4a",
            "high",
        )

    def test_serotype_4av_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrIV", "Xv"}) == (
            "Shigella flexneri serotype 4av",
            "high",
        )

    def test_serotype_5a_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrV"}) == (
            "Shigella flexneri serotype 5a",
            "high",
        )

    def test_serotype_5b_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrV", "gtrX"}) == (
            "Shigella flexneri serotype 5b",
            "high",
        )

    def test_serotype_x_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrX"}) == (
            "Shigella flexneri serotype X",
            "high",
        )

    def test_serotype_xv_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrX", "Xv"}) == (
            "Shigella flexneri serotype Xv (4c)",
            "high",
        )

    def test_serotype_yv_exact(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "Xv"}) == (
            "Shigella flexneri serotype Yv",
            "high",
        )

    def test_medium_branch_extra_gene(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrI", "gtrII"}) == (
            "Shigella flexneri serotype 1a",
            "medium",
        )

    def test_oac_variant_3a(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrX", "Oac"}) == (
            "Shigella flexneri serotype 3a",
            "medium",
        )

    def test_oac_variant_3b_via_oac(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "Oac"}) == (
            "Shigella flexneri serotype 3b",
            "medium",
        )

    def test_oac_variant_3b_via_oac1b(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "Oac1b"}) == (
            "Shigella flexneri serotype 3b",
            "medium",
        )

    def test_oac_variant_4b_via_oac(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrIV", "Oac"}) == (
            "Shigella flexneri serotype 4b",
            "medium",
        )

    def test_oac_variant_4b_via_oac1b(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrIV", "Oac1b"}) == (
            "Shigella flexneri serotype 4b",
            "medium",
        )

    def test_oac_variant_4bv(self):
        assert ss._determine_flexneri_type({"Sf_wzx", "gtrIV", "Oac", "Xv"}) == (
            "Shigella flexneri 4bv",
            "medium",
        )

    def test_novel_serotype_when_unknown_gtr_combo(self):
        serotype, conf = ss._determine_flexneri_type({"Sf_wzx", "gtrI", "gtrII", "gtrIII"})
        assert serotype == "Shigella flexneri (novel serotype)"
        assert conf == "low"

    def test_undetermined_when_no_sf_marker_and_empty_gtr(self):
        assert ss._determine_flexneri_type(set()) == ("Undetermined", "low")


class TestDetermineDysenteriaeType:
    def test_high_both_wzx_wzy(self):
        assert ss._determine_dysenteriae_type({"Sd1_wzx", "Sd1_wzy"}) == (1, "high")

    def test_medium_wzx_only(self):
        assert ss._determine_dysenteriae_type({"Sd1_wzx"}) == (1, "medium")

    def test_medium_wzy_only(self):
        assert ss._determine_dysenteriae_type({"Sd1_wzy"}) == (1, "medium")

    def test_serotype_15_high(self):
        assert ss._determine_dysenteriae_type({"Sd15_wzx", "Sd15_wzy"}) == (15, "high")

    def test_no_numbered_match_prov(self):
        assert ss._determine_dysenteriae_type({"SdProv_wzx"}) == (None, "low")

    def test_no_numbered_match_provE(self):
        assert ss._determine_dysenteriae_type({"SdProvE_wzx"}) == (None, "low")

    def test_totally_unknown(self):
        assert ss._determine_dysenteriae_type({"Sd_mystery"}) == (None, "low")


class TestDetermineBoydiiType:
    def test_high_both_wzx_wzy(self):
        assert ss._determine_boydii_type({"Sb1_wzx", "Sb1_wzy"}) == (1, "high")

    def test_medium_wzx_only(self):
        assert ss._determine_boydii_type({"Sb1_wzx"}) == (1, "medium")

    def test_serotype_20_high(self):
        assert ss._determine_boydii_type({"Sb20_wzx", "Sb20_wzy"}) == (20, "high")

    def test_untypeable_prov(self):
        assert ss._determine_boydii_type({"SbProv_wzx"}) == (None, "low")

    def test_totally_unknown(self):
        assert ss._determine_boydii_type({"Sb_mystery"}) == (None, "low")


class TestSerotypeFlexneri:
    def test_flexneri_1a(self, monkeypatch):
        r = _serotype(monkeypatch, ["Sf_wzx", "gtrI"])
        assert r.species == "Shigella flexneri"
        assert r.serotype == "Shigella flexneri serotype 1a"
        assert r.confidence == "high"
        assert "Shigella flexneri" in r.interpretation
        assert "confidence: high" in r.interpretation

    def test_flexneri_6_via_top_level(self, monkeypatch):
        r = _serotype(monkeypatch, ["Sf6_wzx"])
        assert r.species == "Shigella flexneri"
        assert r.serotype == "Shigella flexneri serotype 6"
        assert r.confidence == "high"


class TestSerotypeSonnei:
    def test_sonnei_high(self, monkeypatch):
        r = _serotype(monkeypatch, ["Ss_wzx", "Ss_wzy"])
        assert r.species == "Shigella sonnei"
        assert r.serotype == "Shigella sonnei"
        assert r.confidence == "high"

    def test_sonnei_medium_wzx_only(self, monkeypatch):
        r = _serotype(monkeypatch, ["Ss_wzx"])
        assert r.species == "Shigella sonnei"
        assert r.confidence == "medium"


class TestSerotypeDysenteriae:
    def test_dysenteriae_1_high(self, monkeypatch):
        r = _serotype(monkeypatch, ["Sd1_wzx", "Sd1_wzy"])
        assert r.species == "Shigella dysenteriae"
        assert r.serotype == "Shigella dysenteriae type 1"
        assert r.confidence == "high"

    def test_dysenteriae_2_medium(self, monkeypatch):
        r = _serotype(monkeypatch, ["Sd2_wzx"])
        assert r.serotype == "Shigella dysenteriae type 2"
        assert r.confidence == "medium"

    def test_dysenteriae_untypeable(self, monkeypatch):
        r = _serotype(monkeypatch, ["SdProv_wzx"])
        assert r.species == "Shigella dysenteriae"
        assert r.serotype == "Shigella dysenteriae (untypeable)"
        assert r.confidence == "low"


class TestSerotypeBoydii:
    def test_boydii_1_high(self, monkeypatch):
        r = _serotype(monkeypatch, ["Sb1_wzx", "Sb1_wzy"])
        assert r.species == "Shigella boydii"
        assert r.serotype == "Shigella boydii type 1"
        assert r.confidence == "high"

    def test_boydii_untypeable(self, monkeypatch):
        r = _serotype(monkeypatch, ["SbProv_wzx"])
        assert r.species == "Shigella boydii"
        assert r.serotype == "Shigella boydii (untypeable)"
        assert r.confidence == "low"


class TestSerotypeEdgeCases:
    def test_no_shigella_signals(self, monkeypatch):
        r = _serotype(monkeypatch, ["stx1", "uidA"])
        assert r.species == "No Shigella serotype determinants"
        assert r.confidence == "low"
        assert "No Shigella O-antigen genes detected" in r.interpretation

    def test_only_ipah_no_species_signal(self, monkeypatch):
        r = _serotype(monkeypatch, ["ipaH_c"])
        assert r.species == "No Shigella serotype determinants"
        assert "ipaH_c" in r.interpretation

    def test_multiple_species_signals(self, monkeypatch):
        r = _serotype(monkeypatch, ["Sf_wzx", "Ss_wzx"])
        assert r.species == "Multiple Shigella species signals: flexneri, sonnei"
        assert r.confidence == "low"
        assert "Mixed serotype signals" in r.interpretation

    def test_eiec_note_present(self, monkeypatch):
        r = _serotype(monkeypatch, ["Sf_wzx", "gtrI", "ipaH_c", "EclacY"])
        assert "EIEC markers present" in r.interpretation

    def test_no_eiec_note_without_ecoli(self, monkeypatch):
        r = _serotype(monkeypatch, ["Sf_wzx", "gtrI", "ipaH_c"])
        assert "EIEC" not in r.interpretation

    def test_detected_genes_sorted(self, monkeypatch):
        r = _serotype(monkeypatch, ["gtrI", "Sf_wzx"])
        assert r.detected_genes == ["Sf_wzx", "gtrI"]

    def test_reads_r2_forwarded_to_scan(self, monkeypatch):
        captured = {}

        def fake_scan(query, **kw):
            captured.update(kw)
            return _scan([])

        monkeypatch.setattr(ss, "scan", fake_scan)
        ss.serotype("/fake/r1.fastq.gz", reads_r2="/fake/r2.fastq.gz")
        assert captured["reads_r2"] == "/fake/r2.fastq.gz"


class TestShigellaSerotypeResultToDict:
    def test_to_dict_keys(self):
        r = ss.ShigellaSerotypeResult(
            species="Shigella sonnei",
            serotype="Shigella sonnei",
            confidence="high",
            detected_genes=["Ss_wzx"],
            interpretation="...",
        )
        d = r.to_dict()
        assert set(d.keys()) == {
            "species",
            "serotype",
            "confidence",
            "detected_genes",
            "interpretation",
        }
        assert d["confidence"] == "high"
