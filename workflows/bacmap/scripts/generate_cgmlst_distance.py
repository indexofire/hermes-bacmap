#!/usr/bin/env python3
"""Compute pairwise Hamming allele-distance matrix for a cgMLST cohort.

Reads a multi-sample cgMLST allele-profile TSV (as produced by the
``cgmlst_cohort_profiles`` Snakemake rule, which merges per-sample
``gmlst typing cgmlst --format tsv`` outputs) and writes a JSON distance
matrix consumed by the ``cgmlst_mst`` and ``cgmlst_summary`` rules.

Distance definition (EnteroBase HierCC convention, Zhou 2020): a locus
contributes 1 iff both samples have a non-None allele call AND the calls
differ; loci missing on either side are excluded (not counted as a
difference, not counted as a match). Implementation delegates to
``hermes_bacmap.analysis.cgmlst_distance.distance_matrix`` so the cohort
pipeline and the per-sample trace-back share a single distance definition.

Pipeline scripts run under the pixi env, which does not install the
``hermes_bacmap`` package; ``src/`` is prepended to ``sys.path`` so the
shared analysis module can be imported (mirrors the convention used by the
vendoring helper, and keeps a single source of truth for distance logic).

Usage:
    python generate_cgmlst_distance.py <profiles.tsv> <distance_matrix.json> \\
        [--group salmonella]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make hermes_bacmap importable under the pixi env (package not installed there).
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "src"))

from hermes_bacmap.analysis.cgmlst_distance import (  # noqa: E402
    DistanceMatrix,
    distance_matrix,
)
from hermes_bacmap.utils import parse_cgmlst_profiles  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a cgMLST pairwise Hamming distance matrix (JSON).",
    )
    parser.add_argument(
        "profiles",
        help="Multi-sample cgMLST TSV (merged per-sample gmlst outputs).",
    )
    parser.add_argument("output", help="Output distance-matrix JSON path.")
    parser.add_argument(
        "--group",
        default=None,
        help="Cohort group name (e.g. salmonella) recorded in the JSON for tracing.",
    )
    args = parser.parse_args()

    profiles_path = Path(args.profiles)
    if not profiles_path.exists():
        print(f"ERROR: profiles not found: {profiles_path}", file=sys.stderr)
        return 1

    profiles = parse_cgmlst_profiles(profiles_path.read_text())
    if len(profiles) < 2:
        print(
            f"ERROR: need >=2 profiles for a cohort distance matrix, "
            f"got {len(profiles)}",
            file=sys.stderr,
        )
        return 1

    matrix: DistanceMatrix = distance_matrix(profiles)

    # allele_distances: flat "sampleA|sampleB" -> int, mirroring the SNP
    # summary's pairwise_distances shape so downstream consumers (report +
    # ingest) can reuse the same lookup convention.
    allele_distances: dict[str, int] = {}
    samples = matrix.samples
    for i in range(len(samples)):
        for j in range(i + 1, len(samples)):
            a, b = samples[i], samples[j]
            allele_distances[f"{a}|{b}"] = matrix.distances[a][b]

    payload: dict[str, object] = {
        "samples": samples,
        "n_samples": len(samples),
        "distances": matrix.distances,
        "allele_distances": allele_distances,
        "scheme": profiles[0].scheme,
        "n_loci": profiles[0].n_total,
    }
    if args.group:
        payload["group"] = args.group

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))

    print(
        f"cgMLST distance matrix: {len(samples)} samples, "
        f"{len(allele_distances)} pairs",
        file=sys.stderr,
    )
    print(f"Written: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
