"""V. cholerae toxin genotyping: ctxA/ompW combination → toxigenic/non-toxigenic.

Species confirmation: ompW(+) = V. cholerae
Toxigenic determination: ctxA(+) = toxigenic (cholera toxin producer)
ctxA(-) = non-toxigenic (environmental strain)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..analysis.gene_scanner import scan

_MIN_IDENTITY = 85.0
_MIN_COVERAGE = 30.0


@dataclass
class CholeraToxinResult:
    species: str = "Unknown"
    toxigenic: bool = False
    ctxa_positive: bool = False
    ompw_positive: bool = False
    confidence: str = "low"
    detected_genes: list[dict[str, Any]] = field(default_factory=list)
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "toxigenic": self.toxigenic,
            "ctxa_positive": self.ctxa_positive,
            "ompw_positive": self.ompw_positive,
            "confidence": self.confidence,
            "detected_genes": self.detected_genes,
            "interpretation": self.interpretation,
        }


def genotype(contigs_fasta: str | Path) -> CholeraToxinResult:
    scan_result = scan(
        contigs_fasta,
        db_name="markers_v2",
        min_identity=_MIN_IDENTITY,
        min_coverage=_MIN_COVERAGE,
    )

    gene_hits: dict[str, dict[str, Any]] = {}
    for hit in scan_result.genes:
        gene = hit.gene.lower()
        if gene not in gene_hits or hit.identity > gene_hits[gene]["identity"]:
            gene_hits[gene] = {
                "gene": hit.gene,
                "identity": hit.identity,
                "coverage": hit.coverage,
            }

    result = CholeraToxinResult()

    result.ompw_positive = "ompw" in gene_hits
    result.ctxa_positive = "ctxa" in gene_hits

    if result.ompw_positive:
        result.species = "Vibrio cholerae"
        if result.ctxa_positive:
            result.toxigenic = True
            result.confidence = "high"
            result.interpretation = (
                "Toxigenic V. cholerae (ctxA+): cholera toxin producer. "
                "Report to public health immediately (notifiable disease, "
                "Class A in China)."
            )
        else:
            result.toxigenic = False
            result.confidence = "medium"
            result.interpretation = (
                "Non-toxigenic V. cholerae (ctxA-): environmental strain, "
                "does not produce cholera toxin. Not a notifiable event."
            )
    elif result.ctxa_positive:
        result.species = "Vibrio spp. (atypical)"
        result.confidence = "medium"
        result.interpretation = "ctxA+ but ompW-: possible mixed sample or atypical strain."
    else:
        result.interpretation = "No V. cholerae markers detected."

    result.detected_genes = list(gene_hits.values())
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="V. cholerae toxin genotyping")
    parser.add_argument("contigs")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    r = genotype(args.contigs)
    if args.json:
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
    else:
        d = r.to_dict()
        print(f"Species: {d['species']}")
        print(f"Toxigenic: {d['toxigenic']}")
        print(f"ctxA: {d['ctxa_positive']}, ompW: {d['ompw_positive']}")
        print(d["interpretation"])


if __name__ == "__main__":
    main()
