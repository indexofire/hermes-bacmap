"""Marker registration — capability evolution registration step.

Additively registers a validated novel marker into marker_rules.yaml (and
optionally appends its sequence to the markers FASTA). Atomic write with
.bak backup of the previous state; idempotent re-registration; species
keys normalized to the underscore convention used by the rules file
(space → underscore, title-case first token preserved).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import yaml

_SPECIES_SAFE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_ -]*$")
_GENE_SAFE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


def _normalize_species(species: str) -> str:
    cleaned = " ".join(species.split())
    if not _SPECIES_SAFE_RE.match(cleaned):
        raise ValueError(f"invalid species name: {species!r}")
    cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned.replace(" ", "_")


def _normalize_gene(gene: str) -> str:
    cleaned = gene.strip()
    if not _GENE_SAFE_RE.match(cleaned):
        raise ValueError(f"invalid gene name: {gene!r}")
    return cleaned.lower()


def register_marker(
    species: str,
    gene: str,
    rules_path: Path | None = None,
    markers_fasta: Path | None = None,
    sequence_fasta: Path | None = None,
    min_identity: int = 90,
    min_hits: int = 1,
) -> dict[str, Any]:
    from ..config import REF_DIR

    if rules_path is None:
        rules_path = REF_DIR / "species" / "marker_rules.yaml"

    species_key = _normalize_species(species)
    gene_key = _normalize_gene(gene)

    if not rules_path.exists():
        raise FileNotFoundError(f"marker rules file not found: {rules_path}")

    with rules_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    rules = data.get("rules") or []
    if not isinstance(rules, list):
        raise ValueError(f"malformed rules file: {rules_path}")

    target = next((r for r in rules if r.get("species") == species_key), None)
    action: str

    if target is None:
        target = {
            "species": species_key,
            "genes": [gene_key],
            "min_hits": min_hits,
            "min_identity": min_identity,
        }
        rules.append(target)
        action = "created"
    elif gene_key in target["genes"]:
        action = "already_present"
    else:
        target["genes"].append(gene_key)
        action = "appended"

    fasta_appended = False
    if sequence_fasta is not None and markers_fasta is not None:
        fasta_appended = _append_sequence(gene_key, sequence_fasta, markers_fasta)

    if action != "already_present":
        backup = rules_path.with_suffix(rules_path.suffix + ".bak")
        shutil.copy2(rules_path, backup)
        data["rules"] = rules
        tmp = rules_path.with_suffix(rules_path.suffix + ".tmp")
        tmp.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        tmp.replace(rules_path)

    return {
        "species": species_key,
        "gene": gene_key,
        "action": action,
        "genes": list(target["genes"]),
        "min_identity": target["min_identity"],
        "min_hits": target["min_hits"],
        "fasta_appended": fasta_appended,
        "rules_path": str(rules_path),
    }


def _append_sequence(gene: str, sequence_fasta: Path, markers_fasta: Path) -> bool:
    if not sequence_fasta.exists():
        raise FileNotFoundError(f"sequence FASTA not found: {sequence_fasta}")

    seq, header = _read_first_record(sequence_fasta)
    existing = markers_fasta.read_text(encoding="utf-8") if markers_fasta.exists() else ""
    if f">{gene}" in existing:
        return False

    with markers_fasta.open("a", encoding="utf-8") as f:
        f.write(f">{header or gene}\n{seq}\n")
    return True


def _read_first_record(fasta: Path) -> tuple[str, str]:
    header = ""
    lines: list[str] = []
    for line in fasta.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if lines:
                break
            header = line[1:].split()[0] if line[1:].split() else ""
        else:
            lines.append(line.strip())
    return "".join(lines), header
