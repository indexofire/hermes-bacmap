"""B. cereus toxin type: nheB (diarrheal) / ces (emetic)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..analysis.gene_scanner import scan

_MIN_IDENTITY = 85.0
_MIN_COVERAGE = 30.0


@dataclass
class BcereusToxinResult:
    species: str = "Unknown"
    toxin_type: str = "non-toxigenic"
    nhe_positive: bool = False
    ces_positive: bool = False
    confidence: str = "low"
    detected_genes: list[str] = field(default_factory=list)
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "toxin_type": self.toxin_type,
            "nhe_positive": self.nhe_positive,
            "ces_positive": self.ces_positive,
            "confidence": self.confidence,
            "detected_genes": self.detected_genes,
            "interpretation": self.interpretation,
        }


def toxin_type(contigs_fasta: str | Path) -> BcereusToxinResult:
    scan_result = scan(
        contigs_fasta,
        db_name="markers_v2",
        min_identity=_MIN_IDENTITY,
        min_coverage=_MIN_COVERAGE,
    )

    genes = {h.gene.lower() for h in scan_result.genes}
    r = BcereusToxinResult(detected_genes=sorted(genes))
    r.nhe_positive = "nheb" in genes
    r.ces_positive = "ces" in genes

    if not r.nhe_positive and not r.ces_positive:
        r.toxin_type = "non-toxigenic"
        r.interpretation = "No diarrheal or emetic toxin genes detected"
        return r

    if r.nhe_positive and r.ces_positive:
        r.toxin_type = "both"
        r.confidence = "high"
        r.interpretation = (
            "Both diarrheal (nhe+) and emetic (ces+) toxin genes — rare dual-type strain"
        )
    elif r.ces_positive:
        r.toxin_type = "emetic"
        r.confidence = "high"
        r.interpretation = "Emetic (ces+): cereulide. Heat-stable, rice/pasta. Vomiting 1-5h."
    elif r.nhe_positive:
        r.toxin_type = "diarrheal"
        r.confidence = "high"
        r.interpretation = "Diarrheal (nhe+): Nhe enterotoxin. Cramps/diarrhea 8-16h."

    return r


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("contigs")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    r = toxin_type(args.contigs)
    if args.json:
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Toxin type: {r.toxin_type}")
        print(r.interpretation)


if __name__ == "__main__":
    main()
