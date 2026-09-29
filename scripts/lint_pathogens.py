#!/usr/bin/env python3
"""Offline consistency checks between pathogens.yaml, markers FASTAs and samples.tsv.

Exit code 0 = clean (warnings allowed); 1 = errors. Reference genomes are
data-layer artifacts (large or downloadable) — missing reference genomes
and marker sequences are WARNINGS, not errors; pass --strict to fail on
warnings too. Run in CI and before
any workflow run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hermes_bacmap.config import PROJECT_ROOT  # noqa: E402
from hermes_bacmap.pathogen_registry import (  # noqa: E402
    RegistryError,
    load_registry,
)

DEFAULT_SAMPLES = PROJECT_ROOT / "workflows/bacmap/config/samples.tsv"
DEFAULT_MARKERS = PROJECT_ROOT / "data/reference/species/markers_v2.fasta"
DEFAULT_LEGACY_MARKERS = PROJECT_ROOT / "data/reference/species/markers.fasta"

_WARNING_PATTERNS = ("reference genome missing", "marker gene")


def _marker_genes_from_fasta(markers_path: Path) -> set[str]:
    genes: set[str] = set()
    if not markers_path.is_file():
        return genes
    for line in markers_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            fields = line[1:].split("~~~")
            if len(fields) >= 2:
                genes.add(fields[1].strip().lower())
    return genes


def is_warning(finding: str) -> bool:
    return any(pat in finding for pat in _WARNING_PATTERNS)


def run_lint(
    registry_path: Path | None,
    samples_path: Path | None,
    markers_path: Path,
    legacy_markers: Path | None = None,
) -> list[str]:
    findings: list[str] = []

    try:
        reg = load_registry(registry_path) if registry_path else load_registry()
    except RegistryError as e:
        return [f"registry invalid: {e}"]

    markers = _marker_genes_from_fasta(markers_path) | _marker_genes_from_fasta(
        legacy_markers or DEFAULT_LEGACY_MARKERS
    )
    if not markers:
        findings.append(f"markers fasta missing or empty: {markers_path}")
    for name, p in reg.pathogens.items():
        if not p.enabled:
            continue
        for gene in p.marker_genes:
            if gene not in markers:
                findings.append(
                    f"pathogen {name!r}: marker gene {gene!r} not found in {markers_path}"
                )

    for name, group in reg.snp_group_specs.items():
        if not group.ref.is_file():
            findings.append(f"snp_group {name!r}: reference genome missing: {group.ref}")

    if samples_path is not None and samples_path.is_file():
        import csv

        with samples_path.open() as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                species = (row.get("species") or "").strip()
                sample = (row.get("sample") or "").strip()
                spec = reg.pathogens.get(species)
                if spec is None:
                    findings.append(f"sample {sample!r}: species {species!r} not in registry")
                elif not spec.enabled:
                    findings.append(
                        f"sample {sample!r}: species {species!r} is disabled in registry"
                    )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES)
    parser.add_argument("--markers", type=Path, default=DEFAULT_MARKERS)
    parser.add_argument("--strict", action="store_true", help="fail on warnings too")
    args = parser.parse_args()

    samples = args.samples if args.samples.exists() else None
    findings = run_lint(args.registry, samples, args.markers)
    errors = [f for f in findings if not is_warning(f)]
    warnings = [f for f in findings if is_warning(f)]
    for f in errors:
        print(f"LINT: {f}")
    for f in warnings:
        print(f"WARN: {f}")
    if errors:
        print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    if warnings:
        print(f"pathogen registry lint: {len(warnings)} warning(s) (0 errors)")
        return 1 if args.strict else 0
    print("pathogen registry lint: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
