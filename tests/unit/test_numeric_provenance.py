"""Unit tests for numeric provenance audit (analysis/provenance.py).

Orphan-claim guard: every number in an AI-generated report must trace to
evidence numbers collected from GOM payloads / tool outputs. Deterministic
regex extraction, no LLM.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.analysis.provenance import (  # noqa: E402
    collect_numbers,
    extract_numeric_claims,
    verify_numeric_provenance,
)


class TestExtractNumericClaims:
    def test_extracts_ratios_percentages_scientific(self):
        text = "tdh 12/12 阳性, q<1e-10, identity 99.5%, p = 2/70, total 384,211 elements"
        claims = extract_numeric_claims(text)

        values = {c.value for c in claims}
        assert 12 in values and 99.5 in values
        assert 1e-10 in values and 70 in values
        assert 384211 in values

        raws = {c.raw for c in claims}
        assert "12/12" in raws
        assert "1e-10" in raws
        assert "384,211" in raws

    def test_exempts_single_digits(self):
        claims = extract_numeric_claims("阶段 3, v2, group A 第 1 批")
        assert claims == []

    def test_keeps_zero_in_ratios(self):
        claims = extract_numeric_claims("0/284 阳性")
        assert any(c.raw == "0/284" for c in claims)


class TestCollectNumbers:
    def test_collects_from_nested_payload(self):
        payload = {
            "result": {
                "genes": [{"gene": "tdh", "p_value": 0.0286, "present_a": 12}],
                "total_clusters": 3847,
            },
            "samples": ["SAM1", "SAM2"],
        }
        evidence = collect_numbers(payload)

        assert 0.0286 in evidence
        assert 12 in evidence
        assert 3847 in evidence


class TestVerifyNumericProvenance:
    def test_all_numbers_traced_passes(self):
        evidence = collect_numbers(
            {"genes": [{"present_a": 12, "present_b": 0, "q": 0.042857}], "n_a": 4}
        )
        text = "tdh 12/4 阳性, q_value 0.0429"

        result = verify_numeric_provenance(text, evidence)

        assert result.passed is True
        assert result.orphans == []

    def test_untraced_number_is_orphaned(self):
        text = "8/25 阳性"
        evidence = collect_numbers({"present_a": 12, "n": 25})

        result = verify_numeric_provenance(text, evidence)

        assert result.passed is False
        orphan_values = {o["value"] for o in result.orphans}
        assert 8 in orphan_values

    def test_rounding_tolerance(self):
        text = "prevalence 33.3%"
        evidence = {1 / 3}

        result = verify_numeric_provenance(text, evidence)

        assert result.passed is True

    def test_empty_text_passes(self):
        assert verify_numeric_provenance("", {1, 2}).passed is True

    def test_to_dict_envelope(self):
        result = verify_numeric_provenance("99/100", {99})
        d = result.to_dict()

        assert d["analysis_type"] == "numeric_provenance"
        assert d["result"]["n_orphans"] == 1
        assert d["result"]["orphans"][0]["raw"] == "100"

    def test_orphan_carries_context(self):
        result = verify_numeric_provenance("检出 88 株阳性", {1})

        orphan = result.orphans[0]
        assert "88" in orphan["raw"]
        assert "阳性" in orphan["context"] or "88" in orphan["context"]
