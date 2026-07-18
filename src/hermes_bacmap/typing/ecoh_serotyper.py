"""E. coli O:H serotype interpretation layer.

Wraps gene_scanner.scan(db_name="ecoh") with O:H antigen parsing.
No BLAST code — all scanning delegated to gene_scanner.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hermes_bacmap.analysis.gene_scanner import scan

_O_PATTERNS = [
    re.compile(r"wzx-O(\S+)"),
    re.compile(r"wzy-O(\S+)"),
    re.compile(r"wzm-O(\S+)"),
    re.compile(r"wzt-O(\S+)"),
]
_H_PATTERNS = [
    re.compile(r"fliC-H(\S+)"),
    re.compile(r"flkA-H(\S+)"),
    re.compile(r"fllA-H(\S+)"),
    re.compile(r"flmA-H(\S+)"),
    re.compile(r"flnA-H(\S+)"),
]


@dataclass
class SerotypeResult:
    o_type: str = "-"
    h_type: str = "-"
    serotype: str = "-:-"
    o_hits: list[dict[str, Any]] = field(default_factory=list)
    h_hits: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "o_type": self.o_type,
            "h_type": self.h_type,
            "serotype": self.serotype,
            "o_antigen_hits": self.o_hits,
            "h_antigen_hits": self.h_hits,
            "interpretation": self._interpret(),
        }

    def _interpret(self) -> str:
        parts = []
        parts.append(
            f"O antigen: O{self.o_type}" if self.o_type != "-" else "No O antigen detected"
        )
        parts.append(
            f"H antigen: H{self.h_type}" if self.h_type != "-" else "No H antigen (non-motile?)"
        )
        parts.append(f"Serotype: {self.serotype}")
        return "; ".join(parts)


def _parse_antigen(gene_name: str) -> tuple[str, str, str] | None:
    for p in _O_PATTERNS:
        m = p.search(gene_name)
        if m:
            return gene_name.split("-")[0], "O", m.group(1).split("-")[0].replace("Gp", "")
    for p in _H_PATTERNS:
        m = p.search(gene_name)
        if m:
            return gene_name.split("-")[0], "H", m.group(1).split("-")[0].replace("Gp", "")
    return None


def serotype(contigs_fasta: str | Path, **kwargs: Any) -> SerotypeResult:
    scan_result = scan(contigs_fasta, db_name="ecoh", **kwargs)

    o_hits: list[dict[str, Any]] = []
    h_hits: list[dict[str, Any]] = []
    o_scores: dict[str, float] = {}
    h_scores: dict[str, float] = {}

    for hit in scan_result.genes:
        parsed = _parse_antigen(hit.gene)
        if not parsed:
            continue
        gene_prefix, antigen_type, antigen_group = parsed
        score = hit.identity * hit.coverage / 100
        entry = {
            "gene": gene_prefix,
            "antigen_group": antigen_group,
            "identity": hit.identity,
            "coverage": hit.coverage,
            "contig": hit.contig,
        }
        if antigen_type == "O":
            o_hits.append(entry)
            if antigen_group not in o_scores or score > o_scores[antigen_group]:
                o_scores[antigen_group] = score
        else:
            h_hits.append(entry)
            if antigen_group not in h_scores or score > h_scores[antigen_group]:
                h_scores[antigen_group] = score

    o_type = max(o_scores, key=o_scores.__getitem__) if o_scores else "-"
    h_type = max(h_scores, key=h_scores.__getitem__) if h_scores else "-"

    return SerotypeResult(
        o_type=o_type,
        h_type=h_type,
        serotype=f"O{o_type}:H{h_type}" if o_type != "-" or h_type != "-" else "-:-",
        o_hits=sorted(o_hits, key=lambda x: -x["identity"]),
        h_hits=sorted(h_hits, key=lambda x: -x["identity"]),
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="E. coli O:H serotyper")
    parser.add_argument("contigs")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = serotype(args.contigs)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        d = result.to_dict()
        print(f"Serotype: {d['serotype']}")
        print(f"O hits: {len(d['o_antigen_hits'])}, H hits: {len(d['h_antigen_hits'])}")
        print(d["interpretation"])


if __name__ == "__main__":
    main()
