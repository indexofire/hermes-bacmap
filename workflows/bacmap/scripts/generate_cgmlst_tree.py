#!/usr/bin/env python3
"""Build a Newick tree from a cgMLST Hamming distance matrix.

Reads the JSON distance matrix produced by ``generate_cgmlst_distance.py``
and writes a Newick tree (default: MST via scipy's
``minimum_spanning_tree`` / Prim's algorithm, matching GrapeTree-style
cgMLST rendering; neighbour-joining is also available). Tree construction
delegates to ``hermes_bacmap.analysis.cgmlst_distance.build_tree`` so the
pipeline and analysis layer share a single validated builder (every tree
round-trips through ``Bio.Phylo.parse``).

Usage:
    python generate_cgmlst_tree.py <distance_matrix.json> <core.treefile> \\
        [--method mst|nj]
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
    build_tree,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a Newick tree from a cgMLST distance matrix JSON.",
    )
    parser.add_argument(
        "matrix",
        help="distance_matrix.json produced by generate_cgmlst_distance.py.",
    )
    parser.add_argument("output", help="Output Newick treefile path.")
    parser.add_argument(
        "--method",
        default="mst",
        choices=("mst", "nj"),
        help=(
            "Tree algorithm: 'mst' (scipy Prim, GrapeTree-style, default) "
            "or 'nj' (pure-Python neighbour-joining, Saitou & Nei 1987)."
        ),
    )
    args = parser.parse_args()

    matrix_path = Path(args.matrix)
    if not matrix_path.exists():
        print(f"ERROR: distance matrix not found: {matrix_path}", file=sys.stderr)
        return 1

    payload = json.loads(matrix_path.read_text())
    samples: list[str] = payload.get("samples", [])
    # JSON keys are always strings; DistanceMatrix is keyed by sample id (str),
    # so the round-trip is type-preserving. Values are int Hamming distances.
    raw_distances = payload.get("distances", {})

    if len(samples) < 2:
        print(
            f"ERROR: need >=2 samples to build a tree, got {len(samples)}",
            file=sys.stderr,
        )
        return 1

    matrix = DistanceMatrix(samples=samples, distances=raw_distances)
    newick = build_tree(matrix, method=args.method)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(newick + "\n")

    print(
        f"cgMLST tree ({args.method}): {len(samples)} taxa",
        file=sys.stderr,
    )
    print(f"Written: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
