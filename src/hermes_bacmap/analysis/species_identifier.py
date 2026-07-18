"""Species identifier — unified pathogen identification from contigs.

Single BLAST scan against species_markers database (invA/uidA/ipaH/toxR/tlh).
Replaces 4 separate Snakemake rules (species_blastn_inva, dec_ipaH_blast,
vpara_targets). Extensible: add new genes to species_markers.fasta to support
new pathogens without changing code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hermes_bacmap.analysis.gene_scanner import scan

_SPECIES_MIN_IDENTITY = 85.0
_SPECIES_MIN_COVERAGE = 30.0

_GENE_TO_SPECIES = {
    "inva": ("Salmonella", "high"),
    "uida": ("DEC", "high"),
    "ipah": ("Shigella/EIEC", "high"),
    "toxr": ("V_parahaemolyticus", "high"),
    "tlh": ("V_parahaemolyticus", "high"),
}

_SPECIES_PRIORITY = ["inva", "ipah", "toxr", "tlh", "uida"]


@dataclass
class SpeciesIdResult:
    species: str = "Unknown"
    confidence: str = "low"
    detected_markers: list[dict[str, Any]] = field(default_factory=list)
    all_hits: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "confidence": self.confidence,
            "detected_markers": self.detected_markers,
            "interpretation": self._interpret(),
        }

    def _interpret(self) -> str:
        if self.species == "Unknown":
            return "No species-specific markers detected"
        markers = [m["gene"] for m in self.detected_markers]
        return f"Identified as {self.species} based on: {', '.join(markers)}"


def identify(contigs_fasta: str | Path, mode: str = "simple") -> SpeciesIdResult | Any:
    if mode == "standard":
        from hermes_bacmap.analysis.taxonomic_validator import validate_genome

        return validate_genome(contigs_fasta, mode="standard")

    scan_result = scan(
        contigs_fasta,
        db_name="species_markers",
        min_identity=_SPECIES_MIN_IDENTITY,
        min_coverage=_SPECIES_MIN_COVERAGE,
    )

    result = SpeciesIdResult()

    gene_hits: dict[str, dict[str, Any]] = {}
    for hit in scan_result.genes:
        gene_lower = hit.gene.lower()
        if gene_lower in _GENE_TO_SPECIES:
            if gene_lower not in gene_hits or hit.identity > gene_hits[gene_lower]["identity"]:
                gene_hits[gene_lower] = {
                    "gene": hit.gene,
                    "identity": hit.identity,
                    "coverage": hit.coverage,
                    "contig": hit.contig,
                }
        result.all_hits.append(
            {
                "gene": hit.gene,
                "identity": hit.identity,
                "coverage": hit.coverage,
            }
        )

    result.detected_markers = [gene_hits[g] for g in _SPECIES_PRIORITY if g in gene_hits]

    if not gene_hits:
        return result

    for gene in _SPECIES_PRIORITY:
        if gene in gene_hits:
            result.species, result.confidence = _GENE_TO_SPECIES[gene]
            break

    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Species identifier")
    parser.add_argument("contigs")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = identify(args.contigs)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        d = result.to_dict()
        print(f"Species: {d['species']} ({d['confidence']})")
        for m in d["detected_markers"]:
            print(f"  {m['gene']}: {m['identity']}% identity, {m['coverage']}% coverage")
        print(d["interpretation"])


if __name__ == "__main__":
    main()
