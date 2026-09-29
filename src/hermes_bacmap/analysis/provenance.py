"""Numeric provenance audit — orphan-claim guard for AI-generated reports.

Every number in a report (ratios, percentages, p/q values, counts) must be
traceable to evidence numbers collected from GOM payloads or tool outputs.
Deterministic regex extraction, tolerance for rounding (3 decimals) and
percent-of-ratio restatement. Single-digit bare integers (structural text
like "阶段 3", "v2") are exempt; digits inside ratios/scientific/percent
tokens are always checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_SCI_RE = re.compile(r"\d+(?:\.\d+)?[eE][+-]?\d+")
_RATIO_RE = re.compile(r"\b(\d{1,9})\s*/\s*(\d{1,9})\b")
_GROUPED_INT_RE = re.compile(r"\d{1,3}(?:,\d{3})+")
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?%")
_DECIMAL_RE = re.compile(r"\d+\.\d+")
_INT_RE = re.compile(r"\d+")
_CONTEXT_CHARS = 24


@dataclass(frozen=True)
class NumericClaim:
    value: float
    raw: str
    start: int
    context: str


@dataclass
class NumericProvenanceResult:
    numbers_checked: int = 0
    orphans: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.orphans

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_type": "numeric_provenance",
            "result": {
                "numbers_checked": self.numbers_checked,
                "n_orphans": len(self.orphans),
                "orphans": self.orphans,
                "passed": self.passed,
            },
        }


def _claim(value: float, raw: str, text: str, start: int) -> NumericClaim:
    ctx_start = max(0, start - _CONTEXT_CHARS)
    ctx_end = min(len(text), start + len(raw) + _CONTEXT_CHARS)
    return NumericClaim(value, raw, start, text[ctx_start:ctx_end].strip())


def extract_numeric_claims(text: str) -> list[NumericClaim]:
    claims: list[NumericClaim] = []
    consumed: list[tuple[int, int]] = []

    def _span_free(start: int, end: int) -> bool:
        return all(end <= s or start >= e for s, e in consumed)

    def _take(match_text: str, start: int, value: float) -> None:
        if _span_free(start, start + len(match_text)):
            claims.append(_claim(value, match_text, text, start))
            consumed.append((start, start + len(match_text)))

    for m in _SCI_RE.finditer(text):
        _take(m.group(0), m.start(), float(m.group(0)))

    for m in _RATIO_RE.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        _take(m.group(0), m.start(), float(a))
        consumed.append((m.start(), m.end()))
        if b >= 10:
            claims.append(_claim(float(b), m.group(2), text, m.start()))

    for m in _GROUPED_INT_RE.finditer(text):
        _take(m.group(0), m.start(), float(m.group(0).replace(",", "")))

    for m in _PERCENT_RE.finditer(text):
        _take(m.group(0), m.start(), float(m.group(0)[:-1]))

    for m in _DECIMAL_RE.finditer(text):
        _take(m.group(0), m.start(), float(m.group(0)))

    for m in _INT_RE.finditer(text):
        if int(m.group(0)) >= 10:
            _take(m.group(0), m.start(), float(m.group(0)))

    claims.sort(key=lambda c: c.start)
    return claims


def collect_numbers(payload: Any) -> set[float]:
    evidence: set[float] = set()

    def _walk(node: Any) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            evidence.add(float(node))
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                _walk(v)
        elif isinstance(node, str):
            stripped = node.replace(",", "")
            try:
                evidence.add(float(stripped))
            except ValueError:
                pass

    _walk(payload)
    return evidence


def _matched(value: float, evidence: set[float], rounded: set[float]) -> bool:
    if value in evidence:
        return True
    r = round(value, 3)
    if r in rounded:
        return True
    return round(value / 100, 3) in rounded


def verify_numeric_provenance(text: str, evidence_numbers: set[float]) -> NumericProvenanceResult:
    rounded = {round(e, 3) for e in evidence_numbers}
    orphans: list[dict[str, Any]] = []

    claims = extract_numeric_claims(text)
    for claim in claims:
        if not _matched(claim.value, evidence_numbers, rounded):
            orphans.append(
                {
                    "value": claim.value,
                    "raw": claim.raw,
                    "context": claim.context,
                }
            )

    return NumericProvenanceResult(
        numbers_checked=len(claims),
        orphans=orphans,
    )
