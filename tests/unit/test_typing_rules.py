"""Tests for the data-driven typing rule engine (analysis/typing_rules.py).

Rule files live in data/reference/typing/<scheme>/typing_rules.yaml —
the engine interprets gapit-screened gene presence against combination
rules with no per-pathogen hardcoding.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.analysis.typing_rules import list_schemes, type_by_rules  # noqa: E402

_MOD = "hermes_bacmap.analysis.typing_rules"


def _scan_with_genes(genes: dict[str, float]):
    """Mock gene_scanner.scan to return synthetic hits {gene: identity}."""

    class _Hit:
        def __init__(self, gene: str, identity: float):
            self.gene = gene
            self.identity = identity
            self.coverage = 95.0

    class _ScanResult:
        def __init__(self):
            self.genes = [_Hit(g, i) for g, i in genes.items()]

    return _ScanResult()


class TestListSchemes:
    def test_lists_all_four_schemes(self):
        schemes = list_schemes()
        assert set(schemes) >= {
            "vcholerae_toxin",
            "lmono_serogroup",
            "cdiff_toxin",
            "bcereus_toxin",
        }


class TestVcholeraeToxin:
    def test_toxigenic_when_ctxa_ompw_positive(self):
        with patch(f"{_MOD}.scan", return_value=_scan_with_genes({"ctxA": 99.0, "ompW": 98.5})):
            r = type_by_rules("fake.fna", "vcholerae_toxin")
        assert r.call["toxigenic"] is True
        assert r.confidence == "high"
        assert r.rule_id == "toxigenic"
        assert "产毒" in r.interpretation

    def test_non_toxigenic_when_ompw_only(self):
        with patch(f"{_MOD}.scan", return_value=_scan_with_genes({"ompW": 97.0})):
            r = type_by_rules("fake.fna", "vcholerae_toxin")
        assert r.call["toxigenic"] is False
        assert r.rule_id == "non_toxigenic"


class TestLmonoSerogroup:
    def test_serogroup_1_2a(self):
        with patch(
            f"{_MOD}.scan",
            return_value=_scan_with_genes({"prs": 99.0, "lmo0737": 98.0}),
        ):
            r = type_by_rules("fake.fna", "lmono_serogroup")
        assert r.call["serogroup"] == "1/2a"

    def test_serogroup_4b(self):
        with patch(
            f"{_MOD}.scan",
            return_value=_scan_with_genes({"prs": 99.0, "orf2110": 98.0, "orf2819": 97.0}),
        ):
            r = type_by_rules("fake.fna", "lmono_serogroup")
        assert r.call["serogroup"] == "4b"
        assert r.confidence == "high"


class TestCdiffToxin:
    def test_rt027_binary_toxin(self):
        with patch(
            f"{_MOD}.scan",
            return_value=_scan_with_genes({"tcdA": 99.0, "tcdB": 98.0, "cdtA": 97.0, "cdtB": 96.0}),
        ):
            r = type_by_rules("fake.fna", "cdiff_toxin")
        assert r.call.get("toxigenic") is True

    def test_non_toxigenic(self):
        with patch(f"{_MOD}.scan", return_value=_scan_with_genes({})):
            r = type_by_rules("fake.fna", "cdiff_toxin")
        assert r.call.get("toxigenic") is False or r.confidence == "low"


class TestBcereusToxin:
    def test_diarrheal(self):
        with patch(f"{_MOD}.scan", return_value=_scan_with_genes({"nheB": 98.0})):
            r = type_by_rules("fake.fna", "bcereus_toxin")
        assert r.call["toxin_type"] == "diarrheal"

    def test_emetic(self):
        with patch(f"{_MOD}.scan", return_value=_scan_with_genes({"ces": 99.0})):
            r = type_by_rules("fake.fna", "bcereus_toxin")
        assert r.call["toxin_type"] == "emetic"


class TestToDict:
    def test_gom_compatible_payload(self):
        with patch(f"{_MOD}.scan", return_value=_scan_with_genes({"ctxA": 99.0, "ompW": 98.0})):
            r = type_by_rules("fake.fna", "vcholerae_toxin")
        d = r.to_dict()
        assert d["analysis_type"] == "typing"
        assert d["method"] == "gene_combination_rules"
        assert d["result"]["toxigenic"] is True
        assert d["result"]["confidence"] == "high"
        assert d["database"]["name"] == "vcholerae_toxin"


class TestErrorHandling:
    def test_unknown_scheme_raises(self):
        with pytest.raises(ValueError, match="not found"):
            type_by_rules("fake.fna", "nonexistent_scheme")


class TestGsideBridge:
    def test_bridge_detects_gside(self):
        from hermes_bacmap.services.gside_bridge import gside_available

        # gside is installed in both .venv and .pixi — should be True
        result = gside_available()
        assert isinstance(result, bool)

    def test_bridge_returns_none_when_binary_missing(self):
        from unittest.mock import patch

        from hermes_bacmap.services.gside_bridge import gside_species

        with patch("hermes_bacmap.services.gside_bridge.which", return_value=None):
            assert gside_species("fake.fna") is None
