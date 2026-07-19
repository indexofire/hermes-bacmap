"""K-mer based locus ranking for the VPA serotyper (sourmash containment)."""

from __future__ import annotations

from typing import Any

MIN_CONTAINMENT = 30.0
KMER_TIEBREAK_MARGIN = 5.0


def rank_loci_by_kmer(
    sketch_mhs: dict[str, Any],
    locus_type_map: dict[str, str],
    type_contigs: dict[str, list[tuple[str, str, int, int]]],
    ltype: str,
) -> list[tuple[str, float]]:
    """Rank candidate loci of type `ltype` by containment against the sample contigs."""
    from sourmash import MinHash

    all_seqs = [entry[1] for entries in type_contigs.values() for entry in entries]
    if not all_seqs:
        return []

    sample_mh = MinHash(n=0, ksize=21, scaled=100)
    for seq in all_seqs:
        sample_mh.add_sequence(seq, force=True)

    scored = []
    for locus_id in sketch_mhs:
        if locus_type_map.get(locus_id) != ltype:
            continue
        ref_mh = sketch_mhs[locus_id]
        containment = ref_mh.contained_by(sample_mh) * 100
        scored.append((locus_id, containment))

    scored.sort(key=lambda x: -x[1])
    return scored


def identify_locus_by_kmer(
    sketch_mhs: dict[str, Any],
    locus_type_map: dict[str, str],
    type_contigs: dict[str, list[tuple[str, str, int, int]]],
    ltype: str,
) -> tuple[str | None, float]:
    """Return the top-ranked locus and its containment, or (None, 0) when nothing ranks."""
    ranked = rank_loci_by_kmer(sketch_mhs, locus_type_map, type_contigs, ltype)
    if not ranked:
        return None, 0
    return ranked[0]
