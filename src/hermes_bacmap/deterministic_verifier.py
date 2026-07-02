"""Deterministic Verifier — project.md §8.2 Layer 2。

非 LLM 的确定性规则校验器。检查分析结果是否符合已知规则。
每个结论必须通过此校验才能进入报告。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_KNOWN_SEROGROUPS = frozenset({
    "A", "B", "C1", "C2-C3", "D1", "D2", "E1", "E4",
    "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "R", "S", "T", "U", "V", "W", "X", "Z", "51", "53", "54", "55", "56", "57", "58", "59", "60", "61", "65", "66",
})

_MLST_LOCI = ("aroC", "dnaN", "hemD", "hisD", "purE", "sucA", "thrA")

_CRITICAL_AMR_PATTERNS = [
    re.compile(r"^mcr-\d", re.IGNORECASE),
    re.compile(r"^bla(NDM|KPC|OXA-48|VIM|IMP)", re.IGNORECASE),
    re.compile(r"^blaCTX-M", re.IGNORECASE),
]


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    checks: list[CheckResult]
    failed_count: int
    needs_human_review: bool


class DeterministicVerifier:
    """project.md §8.2 Layer 2 确定性规则校验。"""

    def verify_species(self, verdict: str) -> CheckResult:
        if verdict == "Salmonella":
            return CheckResult("species", True, f"Species confirmed: {verdict}")
        return CheckResult("species", False, f"Species NOT confirmed: {verdict!r}")

    def verify_mlst(self, st: str, alleles: dict[str, str]) -> CheckResult:
        if not st or st in ("-", "N/A", ""):
            return CheckResult("mlst", False, f"MLST ST missing: {st!r}")

        if not st.lstrip("-").isdigit():
            return CheckResult("mlst", False, f"MLST ST not numeric: {st!r}")

        missing = []
        for locus in _MLST_LOCI:
            val = alleles.get(locus, "-")
            if val in ("-", "", "N/A"):
                missing.append(locus)

        if missing:
            return CheckResult(
                "mlst", False,
                f"MLST alleles missing for: {', '.join(missing)}",
                {"missing_loci": missing},
            )

        return CheckResult(
            "mlst", True,
            f"MLST ST={st}, all 7 loci present",
            {"st": st, "alleles": alleles},
        )

    def verify_serotype(self, serovar: str, serogroup: str) -> CheckResult:
        if not serovar or serovar in ("N/A", ""):
            return CheckResult("serotype", False, "Serovar missing")

        details: dict[str, Any] = {"serovar": serovar}
        if serogroup and serogroup != "-":
            details["serogroup"] = serogroup
            if serogroup not in _KNOWN_SEROGROUPS:
                return CheckResult(
                    "serotype", False,
                    f"Unknown serogroup: {serogroup!r}",
                    details,
                )

        return CheckResult("serotype", True, f"Serovar: {serovar}, serogroup: {serogroup}", details)

    def verify_amr_genes(self, genes: list[str]) -> CheckResult:
        warnings = []
        critical = []

        for gene in genes:
            if not gene or not gene.strip():
                return CheckResult("amr", False, "Empty AMR gene name found")

            for pattern in _CRITICAL_AMR_PATTERNS:
                if pattern.search(gene):
                    critical.append(gene)
                    break

            if len(gene) < 3 or "XXX" in gene.upper() or "FAKE" in gene.upper():
                warnings.append(gene)

        details: dict[str, Any] = {"gene_count": len(genes)}
        if warnings:
            details["warnings"] = warnings
        if critical:
            details["critical_resistance"] = True
            details["critical_genes"] = critical

        msg = f"{len(genes)} AMR genes verified"
        if critical:
            msg += f" (CRITICAL: {', '.join(critical)})"

        return CheckResult("amr", True, msg, details)

    def verify_all(self, summary: dict[str, Any]) -> VerificationResult:
        steps = summary.get("steps", {})

        sp_raw = steps.get("species", {})
        verdict = sp_raw.get("verdict", "") if isinstance(sp_raw, dict) else str(sp_raw)
        species_check = self.verify_species(verdict)

        mlst_raw = steps.get("mlst", "")
        st, alleles = self._parse_mlst(mlst_raw)
        mlst_check = self.verify_mlst(st, alleles)

        sero_raw = steps.get("serotype", {})
        serovar = sero_raw.get("sistr", "N/A") if isinstance(sero_raw, dict) else "N/A"
        serogroup = sero_raw.get("serogroup", "") if isinstance(sero_raw, dict) else ""
        sero_check = self.verify_serotype(serovar, serogroup)

        amr_raw = steps.get("amr", {})
        card_genes = []
        if isinstance(amr_raw, dict):
            card = amr_raw.get("abricate_card", [])
            if isinstance(card, list):
                card_genes = [r.get("GENE", "") for r in card if isinstance(r, dict)]
        amr_check = self.verify_amr_genes(card_genes)

        checks = [species_check, mlst_check, sero_check, amr_check]
        failed = [c for c in checks if not c.passed]

        needs_review = bool(amr_check.details.get("critical_resistance"))

        return VerificationResult(
            passed=len(failed) == 0,
            checks=checks,
            failed_count=len(failed),
            needs_human_review=needs_review,
        )

    @staticmethod
    def _parse_mlst(mlst_text: str) -> tuple[str, dict[str, str]]:
        if not mlst_text or not mlst_text.strip():
            return "", {}

        lines = mlst_text.strip().split("\n")
        if len(lines) < 2:
            return "", {}

        header = lines[0].split("\t")
        data = lines[-1].split("\t")

        loci_map = {l.lower(): l for l in _MLST_LOCI}

        st = ""
        alleles: dict[str, str] = {}

        for i, col_name in enumerate(header):
            if i >= len(data):
                break
            col_lower = col_name.strip().lower()
            val = data[i].strip()
            if col_lower == "st":
                st = val
            elif col_lower in loci_map:
                alleles[loci_map[col_lower]] = val

        return st, alleles
