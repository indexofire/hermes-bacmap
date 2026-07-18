"""Shigella serotyper — gene combination interpretation layer.

Wraps gene_scanner.scan(db_name="shigella_ref") with Shigella serotype
determination logic. Ported from ShigATyper (CFSAN-Biostatistics).

Supports 58 Shigella serotypes:
- S. flexneri: 1a/1b/1c/2a/2av/2b/3a/3b/4a/4av/4b/4bv/5a/5b/X/Xv/6/Y/Yv
- S. sonnei
- S. dysenteriae: 1-15
- S. boydii: 1-20
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hermes_bacmap.analysis.gene_scanner import scan

_FLEXNERI_RULES = [
    ("Shigella flexneri serotype 6", ["Sf6_wzx"]),
    ("Shigella flexneri serotype 1a", ["gtrI"]),
    ("Shigella flexneri serotype 1b", ["gtrI", "Oac1b"]),
    ("Shigella flexneri serotype 1c (7a)", ["gtrI", "gtrIC"]),
    ("Shigella flexneri serotype 7b", ["gtrI", "gtrIC", "Oac1b"]),
    ("Shigella flexneri serotype 2a", ["gtrII"]),
    ("Shigella flexneri 2av", ["gtrII", "Xv"]),
    ("Shigella flexneri serotype 2b", ["gtrII", "gtrX"]),
    ("Shigella flexneri serotype 4a", ["gtrIV"]),
    ("Shigella flexneri serotype 4av", ["gtrIV", "Xv"]),
    ("Shigella flexneri serotype 5a", ["gtrV"]),
    ("Shigella flexneri serotype 5b", ["gtrV", "gtrX"]),
    ("Shigella flexneri serotype X", ["gtrX"]),
    ("Shigella flexneri serotype Xv (4c)", ["gtrX", "Xv"]),
    ("Shigella flexneri serotype Yv", ["Xv"]),
    ("Shigella flexneri serotype Y", []),
]

_FLEXNERI_OAC_VARIANTS = {
    "Shigella flexneri serotype 3a": (["gtrX", "Oac"],),
    "Shigella flexneri serotype 3b": (["Oac"], ["Oac1b"]),
    "Shigella flexneri serotype 4b": (["gtrIV", "Oac"], ["gtrIV", "Oac1b"]),
    "Shigella flexneri 4bv": (["gtrIV", "Oac", "Xv"],),
}


@dataclass
class ShigellaSerotypeResult:
    species: str = "Unknown"
    serotype: str = "Undetermined"
    confidence: str = "low"
    detected_genes: list[str] = field(default_factory=list)
    interpretation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "serotype": self.serotype,
            "confidence": self.confidence,
            "detected_genes": self.detected_genes,
            "interpretation": self.interpretation,
        }


def _determine_flexneri_type(detected: set[str]) -> tuple[str, str]:
    gtr_genes = {g for g in detected if g.startswith("gtr") or g in ("Oac", "Oac1b", "Xv")}
    has_sf6 = "Sf6_wzx" in detected
    has_sf = "Sf_wzx" in detected or "Sf_wzy" in detected

    if has_sf6:
        return "Shigella flexneri serotype 6", "high"

    # Exact matches before near-matches: a more specific rule must win over
    # a subset rule regardless of declaration order.
    for serotype, required in _FLEXNERI_RULES:
        if required and set(required) == gtr_genes:
            return serotype, "high"

    for serotype, alternatives in _FLEXNERI_OAC_VARIANTS.items():
        for alt in alternatives:
            if set(alt) == gtr_genes:
                return serotype, "medium"

    near = sorted((r for r in _FLEXNERI_RULES if r[1]), key=lambda r: -len(r[1]))
    for serotype, required in near:
        req_set = set(required)
        if req_set <= gtr_genes and len(req_set) >= len(gtr_genes) - 1:
            return serotype, "medium"

    for serotype, alternatives in _FLEXNERI_OAC_VARIANTS.items():
        for alt in alternatives:
            if set(alt) <= gtr_genes:
                return serotype, "medium"

    if has_sf:
        if not gtr_genes:
            return "Shigella flexneri serotype Y", "high"
        return "Shigella flexneri (novel serotype)", "low"

    return "Undetermined", "low"


def _determine_dysenteriae_type(detected: set[str]) -> tuple[int | None, str]:
    for i in range(1, 16):
        wzx = f"Sd{i}_wzx"
        wzy = f"Sd{i}_wzy"
        if wzx in detected and wzy in detected:
            return i, "high"
        if wzx in detected or wzy in detected:
            return i, "medium"
    for prefix in ("SdProv_", "SdProvE_"):
        if f"{prefix}wzx" in detected:
            return None, "low"
    return None, "low"


def _determine_boydii_type(detected: set[str]) -> tuple[int | None, str]:
    for i in range(1, 21):
        wzx = f"Sb{i}_wzx"
        wzy = f"Sb{i}_wzy"
        if wzx in detected and wzy in detected:
            return i, "high"
        if wzx in detected or wzy in detected:
            return i, "medium"
    if "SbProv_wzx" in detected:
        return None, "low"
    return None, "low"


def serotype(
    query: str | Path,
    reads_r2: str | Path | None = None,
    **kwargs: Any,
) -> ShigellaSerotypeResult:
    scan_result = scan(query, db_name="shigella_ref", reads_r2=reads_r2, **kwargs)
    detected = set(scan_result.unique_genes)

    result = ShigellaSerotypeResult(detected_genes=sorted(detected))

    has_ipah = "ipaH_c" in detected or "ipaB" in detected
    has_sf = "Sf_wzx" in detected or "Sf_wzy" in detected or "Sf6_wzx" in detected
    has_ss = "Ss_wzx" in detected or "Ss_wzy" in detected
    has_sd = any(g.startswith("Sd") for g in detected)
    has_sb = any(g.startswith("Sb") for g in detected)
    has_ecoli = "EclacY" in detected

    species_hits = []
    if has_sf:
        species_hits.append("flexneri")
    if has_ss:
        species_hits.append("sonnei")
    if has_sd:
        species_hits.append("dysenteriae")
    if has_sb:
        species_hits.append("boydii")

    if len(species_hits) == 0:
        result.species = "No Shigella serotype determinants"
        result.interpretation = (
            f"No Shigella O-antigen genes detected. Detected: {', '.join(sorted(detected)[:10])}"
        )
        return result

    if len(species_hits) > 1:
        result.species = f"Multiple Shigella species signals: {', '.join(species_hits)}"
        result.confidence = "low"
        result.interpretation = "Mixed serotype signals — possible contamination or assembly error"
        return result

    sp = species_hits[0]

    if sp == "flexneri":
        serotype_str, conf = _determine_flexneri_type(detected)
        result.species = "Shigella flexneri"
        result.serotype = serotype_str
        result.confidence = conf
    elif sp == "sonnei":
        result.species = "Shigella sonnei"
        result.serotype = "Shigella sonnei"
        result.confidence = "high" if ("Ss_wzx" in detected and "Ss_wzy" in detected) else "medium"
    elif sp == "dysenteriae":
        st_num, conf = _determine_dysenteriae_type(detected)
        result.species = "Shigella dysenteriae"
        result.serotype = (
            f"Shigella dysenteriae type {st_num}" if st_num else "Shigella dysenteriae (untypeable)"
        )
        result.confidence = conf
    elif sp == "boydii":
        st_num, conf = _determine_boydii_type(detected)
        result.species = "Shigella boydii"
        result.serotype = (
            f"Shigella boydii type {st_num}" if st_num else "Shigella boydii (untypeable)"
        )
        result.confidence = conf

    eiec_note = ""
    if has_ecoli and has_ipah:
        eiec_note = " (EIEC markers present — may be EIEC rather than Shigella)"

    result.interpretation = (
        f"{result.species} {result.serotype} (confidence: {result.confidence}){eiec_note}"
    )

    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Shigella serotyper")
    parser.add_argument("contigs")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = serotype(args.contigs)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        d = result.to_dict()
        print(f"Species: {d['species']}")
        print(f"Serotype: {d['serotype']}")
        print(f"Confidence: {d['confidence']}")
        print(f"Genes: {', '.join(d['detected_genes'])}")
        print(d["interpretation"])


if __name__ == "__main__":
    main()
