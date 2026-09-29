"""L. monocytogenes serogrouping via Doumith marker genes (lmo1118/lmo0737/ORF2110/ORF2819/Prs).

Ported from LisSero (MDU-PHL) logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..analysis.gene_scanner import scan

_MIN_IDENTITY = 90.0
_MIN_COVERAGE = 50.0

_SEROGROUP_RULES = [
    (("lmo1118", "-", "-", "lmo0737"), "1/2a"),
    (("-", "-", "lmo0737"), "1/2a"),
    (("ORF2819", "-", "lmo0737"), "1/2b"),
    (("lmo1118", "ORF2110"), "1/2c"),
    (("ORF2110", "ORF2819"), "4b"),
]

_MARKER_GENES = ["lmo1118", "lmo0737", "orf2110", "orf2819", "prs"]


@dataclass
class LmonoSerogroupResult:
    species: str = "Unknown"
    serogroup: str = "Nontypeable"
    confidence: str = "low"
    detected_genes: dict[str, bool] = field(default_factory=dict)
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "serogroup": self.serogroup,
            "confidence": self.confidence,
            "detected_genes": self.detected_genes,
            "interpretation": self.interpretation,
        }


def serogroup(contigs_fasta: str | Path) -> LmonoSerogroupResult:
    scan_result = scan(
        contigs_fasta,
        db_name="markers_v2",
        min_identity=_MIN_IDENTITY,
        min_coverage=_MIN_COVERAGE,
    )

    present: dict[str, bool] = {g: False for g in _MARKER_GENES}
    for hit in scan_result.genes:
        gene = hit.gene.lower()
        if gene in present:
            present[gene] = True

    result = LmonoSerogroupResult(detected_genes=present)

    if not present.get("prs"):
        result.interpretation = "Prs not detected — likely not Listeria monocytogenes"
        return result

    result.species = "Listeria monocytogenes"

    lmo1118 = present.get("lmo1118", False)
    lmo0737 = present.get("lmo0737", False)
    orf2110 = present.get("orf2110", False)
    orf2819 = present.get("orf2819", False)

    if lmo0737 and not orf2110 and not orf2819:
        result.serogroup = "1/2a"
        result.confidence = "high"
    elif orf2819 and lmo0737 and not lmo1118 and not orf2110:
        result.serogroup = "1/2b"
        result.confidence = "high"
    elif lmo1118 and orf2110 and not lmo0737:
        result.serogroup = "1/2c"
        result.confidence = "high"
    elif orf2110 and orf2819 and not lmo1118 and not lmo0737:
        result.serogroup = "4b"
        result.confidence = "high"
    elif lmo1118 and orf2110 and lmo0737:
        result.serogroup = "4b (variant)"
        result.confidence = "medium"
    else:
        result.serogroup = "Nontypeable"
        result.confidence = "low"

    if result.serogroup != "Nontypeable":
        clinical = {
            "1/2a": "most common clinical serogroup",
            "1/2b": "associated with sporadic listeriosis",
            "1/2c": "often food-associated, less invasive",
            "4b": "most associated with outbreaks and high mortality",
        }
        note = clinical.get(result.serogroup, "")
        result.interpretation = f"Serogroup {result.serogroup}" + (f" — {note}" if note else "")
    else:
        result.interpretation = (
            "All 5 markers detected but no known pattern — possible novel serogroup"
        )

    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="L. monocytogenes serogrouping")
    parser.add_argument("contigs")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    r = serogroup(args.contigs)
    if args.json:
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Species: {r.species}, Serogroup: {r.serogroup} ({r.confidence})")
        print(f"Genes: {r.detected_genes}")
        print(r.interpretation)


if __name__ == "__main__":
    main()
