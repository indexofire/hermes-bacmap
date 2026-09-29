"""C. difficile toxin typing: tcdA/tcdB/cdtA/cdtB combination → toxigenic status + RT027 flag."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..analysis.gene_scanner import scan

_MIN_IDENTITY = 85.0
_MIN_COVERAGE = 30.0


@dataclass
class CdiffToxinResult:
    species: str = "Unknown"
    toxigenic: bool = False
    tcda_positive: bool = False
    tcdb_positive: bool = False
    binary_toxin: bool = False
    possible_rt027: bool = False
    toxinotype: str = "non-toxigenic"
    confidence: str = "low"
    detected_genes: list[str] = field(default_factory=list)
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "toxigenic": self.toxigenic,
            "tcda_positive": self.tcda_positive,
            "tcdb_positive": self.tcdb_positive,
            "binary_toxin": self.binary_toxin,
            "possible_rt027": self.possible_rt027,
            "toxinotype": self.toxinotype,
            "confidence": self.confidence,
            "detected_genes": self.detected_genes,
            "interpretation": self.interpretation,
        }


def toxin_type(contigs_fasta: str | Path) -> CdiffToxinResult:
    scan_result = scan(
        contigs_fasta,
        db_name="markers_v2",
        min_identity=_MIN_IDENTITY,
        min_coverage=_MIN_COVERAGE,
    )

    genes_present: set[str] = set()
    for hit in scan_result.genes:
        genes_present.add(hit.gene.lower())

    r = CdiffToxinResult(detected_genes=sorted(genes_present))
    r.tcda_positive = "tcda" in genes_present
    r.tcdb_positive = "tcdb" in genes_present
    r.binary_toxin = "cdta" in genes_present or "cdtb" in genes_present

    if not r.tcda_positive and not r.tcdb_positive:
        r.toxigenic = False
        r.species = "Clostridioides difficile" if "tpa" in str(genes_present) else "Unknown"
        r.toxinotype = "non-toxigenic"
        r.interpretation = "Non-toxigenic C. difficile (tcdA- tcdB-) — not clinically significant"
        return r

    r.species = "Clostridioides difficile"
    r.toxigenic = True

    if r.tcda_positive and r.tcdb_positive:
        if r.binary_toxin:
            r.toxinotype = "toxigenic + binary toxin"
            r.possible_rt027 = True
            r.confidence = "high"
            r.interpretation = (
                "Toxigenic C. difficile with binary toxin (cdt+): "
                "consistent with hypervirulent RT027/BI/NAP1 strain. "
                "Associated with increased severity, recurrence, and "
                "fluoroquinolone resistance. Infection control escalation recommended."
            )
        else:
            r.toxinotype = "toxigenic (tcdA+ tcdB+)"
            r.confidence = "high"
            r.interpretation = "Toxigenic C. difficile (tcdA+ tcdB+): classic toxin producer"
    elif r.tcdb_positive and not r.tcda_positive:
        r.toxinotype = "tcdA- tcdB+ (atypical)"
        r.confidence = "medium"
        r.interpretation = (
            "Atypical toxigenic C. difficile (tcdA- tcdB+): some strains with tcdA deletions"
        )
    elif r.tcda_positive and not r.tcdb_positive:
        r.toxinotype = "tcdA+ tcdB- (unusual)"
        r.confidence = "low"
        r.interpretation = "Unusual pattern (tcdA+ tcdB-): verify with repeat testing"

    return r


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="C. difficile toxin typing")
    parser.add_argument("contigs")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    r = toxin_type(args.contigs)
    if args.json:
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Species: {r.species}, Toxigenic: {r.toxigenic}, RT027: {r.possible_rt027}")
        print(f"Toxinotype: {r.toxinotype}")
        print(r.interpretation)


if __name__ == "__main__":
    main()
