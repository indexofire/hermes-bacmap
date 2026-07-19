"""Gene-level verification for the VPA serotyper (minimap2 coverage/identity)."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from typing import Any

from ._vpa_report import build_gene_result

logger = logging.getLogger(__name__)

MAX_GENE_DIFF = 4
MIN_CONTIG_ALIGN_LEN = 500
MIN_GENE_COV = 30.0

ANTIGEN_BOUNDARY = {
    "O": {"start": "coaD", "end": "rfaD"},
    "K": {"start": "rfaD", "end": "glpX"},
}

_COMP = str.maketrans("ATGCatgc", "TACGtacg")


class _RefFasta:
    """Cached id -> sequence view of the reference locus FASTA.

    Loads the whole file lazily on first access instead of re-scanning it
    per lookup. The first record wins for duplicate ids.
    """

    def __init__(self, mp: Any, fasta_path: str) -> None:
        self._mp = mp
        self._fasta_path = fasta_path
        self._seqs: dict[str, str] | None = None

    def _load(self) -> dict[str, str]:
        if self._seqs is None:
            seqs: dict[str, str] = {}
            for name, seq, _ in self._mp.fastx_read(self._fasta_path):
                seqs.setdefault(name.split()[0], seq)
            self._seqs = seqs
        return self._seqs

    def get(self, locus_id: str) -> str | None:
        """Return the sequence for `locus_id`, or None if absent."""
        return self._load().get(locus_id)

    def all(self) -> dict[str, str]:
        """Return the full cached id -> sequence mapping."""
        return self._load()


def _gene_seq(seq: str, gene: dict[str, Any], comp: dict[int, int]) -> str:
    """Extract a gene's sequence from a locus sequence (reverse-complemented if strand -1)."""
    gseq = seq[gene["start"] : gene["end"]]
    if gene.get("strand", 1) == -1:
        gseq = gseq[::-1].translate(comp)
    return gseq


def _best_hit_cov(aligner: Any, g_seq: str) -> tuple[float, float]:
    """Return (coverage %, identity %) of the best minimap2 hit of `g_seq`, or (0.0, 0.0)."""
    best_cov = best_ident = 0.0
    for h in aligner.map(g_seq):
        cov = 100.0 * h.blen / len(g_seq) if g_seq else 0
        if cov > best_cov:
            best_cov = cov
            best_ident = 100.0 * h.mlen / h.blen if h.blen else 0
    return best_cov, best_ident


def decide(
    gene_diff: int,
    gene_coverage: float,
    identity: float,
    pieces: int,
    missing_boundary: list[str],
) -> tuple[bool, str]:
    """Decide typeability and confidence tier from gene-level metrics."""
    if missing_boundary:
        return False, "Unknown"
    if gene_diff > MAX_GENE_DIFF:
        return False, "Unknown"

    if pieces <= 1 and gene_diff == 0 and identity > 95:
        return True, "Perfect"
    if gene_diff <= 1 and gene_coverage > 90 and identity > 90:
        return True, "High"
    if gene_diff <= MAX_GENE_DIFF and identity > 80:
        return True, "Medium"
    return True, "Low"


def select_by_gene_coverage(
    mp: Any,
    metadata: dict[str, Any],
    ref_fasta: _RefFasta,
    candidates: list[str],
    sample_aligner: Any,
) -> str:
    """Pick the candidate locus with the most genes present in the sample."""
    scores: dict[str, tuple[float, int, float]] = {}

    for lid in candidates:
        meta = metadata.get(lid)
        if not meta:
            continue

        locus_seq = ref_fasta.get(lid)
        if not locus_seq:
            continue

        present = 0
        total_ident = 0.0
        total_genes = len(meta["genes"])

        for gene in meta["genes"]:
            g_seq = _gene_seq(locus_seq, gene, _COMP)
            best_cov, best_ident = _best_hit_cov(sample_aligner, g_seq)

            if best_cov >= MIN_GENE_COV:
                present += 1
                total_ident += best_ident

        gene_cov = present / total_genes * 100 if total_genes else 0
        avg_ident = total_ident / present if present else 0
        scores[lid] = (gene_cov, present, avg_ident)

        logger.debug(
            f"  Gene tiebreak: {lid} = {present}/{total_genes}"
            f" ({gene_cov:.1f}%) ident={avg_ident:.1f}%"
        )

    if not scores:
        return candidates[0]

    return max(scores, key=lambda x: (scores[x][0], scores[x][1], scores[x][2]))


def check_superset_override(
    mp: Any,
    metadata: dict[str, Any],
    locus_type_map: dict[str, str],
    ref_fasta: _RefFasta,
    best_locus: str,
    ltype: str,
    valid_ids: set[str],
    sample_aligner: Any,
) -> str | None:
    """Switch to a superset locus when its unique genes are present in the sample."""
    best_genes = metadata.get(best_locus, {}).get("genes", [])
    if not best_genes:
        return None

    candidates = [
        lid
        for lid in valid_ids
        if lid != best_locus
        and locus_type_map.get(lid) == ltype
        and len(metadata.get(lid, {}).get("genes", [])) > len(best_genes)
    ]
    if not candidates:
        return None

    best_seq = ref_fasta.get(best_locus) or ""
    if not best_seq:
        return None

    best_aligner = mp.Aligner(seq=best_seq, preset="splice")

    present_indices = {
        i
        for i, g in enumerate(best_genes)
        if _best_hit_cov(sample_aligner, _gene_seq(best_seq, g, _COMP))[0] >= 30.0
    }

    def present_genes_are_subset(aligner_b: Any) -> bool:
        for i in present_indices:
            gseq = _gene_seq(best_seq, metadata[best_locus]["genes"][i], _COMP)
            if _best_hit_cov(aligner_b, gseq)[0] < 30.0:
                return False
        return True

    seqs = ref_fasta.all()

    for lid in candidates:
        cand_seq = seqs.get(lid, "")
        if not cand_seq:
            continue

        cand_aligner = mp.Aligner(seq=cand_seq, preset="splice")

        if not present_genes_are_subset(cand_aligner):
            continue

        cand_unique_present = 0
        cand_unique_total = 0
        for g in metadata[lid]["genes"]:
            gseq = _gene_seq(cand_seq, g, _COMP)
            if _best_hit_cov(best_aligner, gseq)[0] >= 30.0:
                continue

            cand_unique_total += 1
            if _best_hit_cov(sample_aligner, gseq)[0] >= 80.0:
                cand_unique_present += 1

        if cand_unique_total > 0 and cand_unique_present >= cand_unique_total * 0.5:
            logger.debug(
                f"  Superset override: {best_locus} is subset of {lid}, "
                f"{lid} unique genes {cand_unique_present}/{cand_unique_total}"
                f" present -> switch to {lid}"
            )
            return lid

    return None


def count_unique_genes(
    mp: Any,
    metadata: dict[str, Any],
    lid_a: str,
    lid_b: str,
    seq_cache: dict[str, str],
    sample_aligner: Any,
    comp: dict[int, int],
) -> tuple[int, int]:
    """Count genes unique to locus A (vs locus B) that are present in the sample."""
    genes_a = metadata.get(lid_a, {}).get("genes", [])
    seq_a = seq_cache.get(lid_a, "")
    seq_b = seq_cache.get(lid_b, "")
    if not seq_a or not seq_b:
        return 0, 0

    aln_b = mp.Aligner(seq=seq_b, preset="splice")
    unique: list[str] = []
    for g in genes_a:
        gseq = _gene_seq(seq_a, g, comp)
        if _best_hit_cov(aln_b, gseq)[0] >= 30.0:
            continue
        unique.append(gseq)

    present = 0
    for gseq in unique:
        if _best_hit_cov(sample_aligner, gseq)[0] >= 80.0:
            present += 1

    return present, len(unique)


def resolve_variant_locus(
    mp: Any,
    metadata: dict[str, Any],
    locus_type_map: dict[str, str],
    ref_fasta: _RefFasta,
    best_locus: str,
    ltype: str,
    type_contigs: dict[str, list[tuple[str, str, int, int]]],
    sample_aligner: Any,
    valid_ids: set[str] | None = None,
) -> str | None:
    """Resolve OLnVn locus by checking presence of locus-unique genes only."""
    m = re.match(r"^(.+?)V\d+$", best_locus)
    if not m:
        return None
    base = m.group(1)

    candidates = [
        lid
        for lid in metadata
        if locus_type_map.get(lid) == ltype
        and (lid == base or re.match(rf"^{re.escape(base)}V\d+$", lid))
        and (valid_ids is None or lid in valid_ids)
    ]
    if len(candidates) < 2:
        return None

    locus_seqs = {lid: seq for lid, seq in ref_fasta.all().items() if lid in candidates}

    locus_aligners = {lid: mp.Aligner(seq=seq, preset="splice") for lid, seq in locus_seqs.items()}

    def sample_identity(g_seq: str) -> float:
        best = 0.0
        for h in sample_aligner.map(g_seq):
            cov = 100.0 * h.blen / len(g_seq) if g_seq else 0
            if cov >= MIN_GENE_COV:
                ident = 100.0 * h.mlen / h.blen if h.blen else 0
                if ident > best:
                    best = ident
        return best

    votes: dict[str, int] = {lid: 0 for lid in candidates}
    vote_log: list[str] = []

    for lid_a in candidates:
        other_lids = [loc for loc in candidates if loc != lid_a]
        for gene in metadata[lid_a]["genes"]:
            g_seq = _gene_seq(locus_seqs[lid_a], gene, _COMP)
            if any(_best_hit_cov(locus_aligners[olid], g_seq)[0] >= 30.0 for olid in other_lids):
                continue

            si = sample_identity(g_seq)
            if si >= 80.0:
                votes[lid_a] += 1
                vote_log.append(f"{gene['name']}({lid_a}): unique, sample={si:.1f}% -> +{lid_a}")

    for line in vote_log:
        logger.debug(f"  Vote: {line}")
    for lid in candidates:
        logger.debug(f"  {lid}: {votes[lid]} votes")

    best_lid = max(votes, key=votes.__getitem__)
    tied = [lid for lid in candidates if lid != best_lid and votes[lid] == votes[best_lid]]
    if tied:
        logger.debug("  -> TIE, keeping k-mer result")
        return None

    if votes[best_lid] == 0:
        return None

    logger.debug(f"  -> Winner: {best_lid}")
    return best_lid


def build_locus_region_aligner(mp: Any, entries: list[tuple[str, str, int, int]]) -> Any:
    """Build a minimap2 aligner over the extracted locus-region contigs (None if empty)."""
    if not entries:
        return None

    tmp = tempfile.NamedTemporaryFile(suffix=".fasta", delete=False, mode="w")
    for i, entry in enumerate(entries):
        tmp.write(f">region_{i}\n{entry[1]}\n")
    tmp.close()
    aligner = mp.Aligner(tmp.name, preset="splice")
    os.unlink(tmp.name)
    return aligner


def find_other_genes_in_locus(
    mp: Any,
    metadata: dict[str, Any],
    locus_type_map: dict[str, str],
    ref_fasta: _RefFasta,
    best_locus: str,
    ltype: str,
    locus_region_aligner: Any,
    occupied_regions: list[tuple[str, int, int]],
    sample_aligner: Any,
) -> list[str]:
    """Find genes from other same-type loci that align inside the best locus region."""
    if not locus_region_aligner:
        return []

    other_loci = [lid for lid in metadata if locus_type_map.get(lid) == ltype and lid != best_locus]

    all_seqs_cache = ref_fasta.all()

    best_seq = all_seqs_cache.get(best_locus, "")

    best_aligner = None
    if best_seq:
        best_aligner = mp.Aligner(seq=best_seq, preset="splice")

    results: list[str] = []
    seen_genes: set[str] = set()
    for lid in other_loci:
        lseq = all_seqs_cache.get(lid)
        if not lseq:
            continue
        for gene in metadata[lid]["genes"]:
            gname = gene.get("locus_tag", gene["name"])
            if gname in seen_genes:
                continue
            g_seq = _gene_seq(lseq, gene, _COMP)
            if not g_seq:
                continue

            if best_aligner and _best_hit_cov(best_aligner, g_seq)[0] >= 30.0:
                continue

            hits_in_region = list(locus_region_aligner.map(g_seq))
            if not hits_in_region:
                continue

            best_hit = max(hits_in_region, key=lambda h: h.blen)
            cov = 100.0 * best_hit.blen / len(g_seq)
            if cov < MIN_GENE_COV:
                continue
            ident = 100.0 * best_hit.mlen / best_hit.blen if best_hit.blen else 0
            results.append(f"{gname},{ident:.2f}%,{cov:.2f}%")
            seen_genes.add(gname)

    return results


def gene_level_analysis(
    mp: Any,
    metadata: dict[str, Any],
    locus_type_map: dict[str, str],
    ref_fasta: _RefFasta,
    best_locus: str,
    type_contigs: dict[str, list[tuple[str, str, int, int]]],
    containment: float,
    sample_aligner: Any,
) -> dict[str, Any]:
    """Run per-gene coverage/identity analysis of the sample against the best locus."""
    meta = metadata[best_locus]
    ltype = meta.get("type", "?")

    locus_seq = ref_fasta.get(best_locus)

    locus_ctg_names = {entry[0] for entry in type_contigs.get(best_locus, [])}
    locus_ctg_total_bp = sum(len(entry[1]) for entry in type_contigs.get(best_locus, []))

    gene_results = []
    missing_genes = []
    expected_in_locus = []
    expected_outside = []
    truncated = []

    name_to_tag = {g["name"]: g.get("locus_tag", g["name"]) for g in meta["genes"]}

    for gene in meta["genes"]:
        g_name = gene.get("locus_tag", gene["name"])

        if not locus_seq:
            missing_genes.append(g_name)
            gene_results.append({"gene": g_name, "identity": 0, "coverage": 0, "status": "missing"})
            continue

        g_seq = _gene_seq(locus_seq, gene, _COMP)

        best_cov = best_ident = 0.0
        best_ctg = ""
        best_r_st = best_r_en = 0
        in_locus_hit = False

        for h in sample_aligner.map(g_seq):
            cov = 100.0 * h.blen / len(g_seq) if g_seq else 0
            if cov > best_cov:
                best_cov = cov
                best_ident = 100.0 * h.mlen / h.blen if h.blen else 0
                best_ctg = h.ctg
                best_r_st = min(h.r_st, h.r_en)
                best_r_en = max(h.r_st, h.r_en)
                in_locus_hit = h.ctg in locus_ctg_names

        if best_cov >= MIN_GENE_COV:
            gd = {
                "gene": g_name,
                "identity": round(best_ident, 2),
                "coverage": round(best_cov, 2),
                "status": "present",
                "ctg": best_ctg,
                "r_st": best_r_st,
                "r_en": best_r_en,
            }
            gene_results.append(gd)
            entry = f"{g_name},{best_ident:.2f}%,{best_cov:.2f}%"
            if in_locus_hit:
                expected_in_locus.append(entry)
            else:
                expected_outside.append(entry)
            if best_cov < 100.0:
                truncated.append(entry)
        else:
            missing_genes.append(g_name)
            gene_results.append({"gene": g_name, "identity": 0, "coverage": 0, "status": "missing"})

    occupied_regions: list[tuple[str, int, int]] = [
        (g["ctg"], g["r_st"], g["r_en"])
        for g in gene_results
        if g["status"] == "present" and g.get("ctg")
    ]

    locus_region_aligner = build_locus_region_aligner(mp, type_contigs.get(best_locus, []))

    other_in_locus = find_other_genes_in_locus(
        mp,
        metadata,
        locus_type_map,
        ref_fasta,
        best_locus,
        ltype,
        locus_region_aligner,
        occupied_regions,
        sample_aligner,
    )

    boundary = ANTIGEN_BOUNDARY.get(ltype, {})
    boundary_tags = {name_to_tag.get(g, g) for g in boundary.values()}
    missing_boundary = [t for t in boundary_tags if t in missing_genes]

    gene_diff = len(missing_genes)
    present = [g for g in gene_results if g["status"] == "present"]
    identity = sum(g["identity"] for g in present) / len(present) if present else 0
    ctgs = {g.get("ctg", "") for g in present if g.get("ctg")}
    pieces = len(ctgs) if ctgs else 0
    gene_coverage = len(present) / len(gene_results) * 100 if gene_results else 0
    ref_len = len(locus_seq) if locus_seq else 0
    len_disc = locus_ctg_total_bp - ref_len

    typeable, confidence = decide(gene_diff, gene_coverage, identity, pieces, missing_boundary)

    alerts = []
    if pieces > 1:
        alerts.append("Fragmented")
    if missing_boundary:
        alerts.append(f"MissingBoundary({','.join(missing_boundary)})")

    return build_gene_result(
        best_locus,
        confidence,
        gene_coverage,
        identity,
        missing_genes,
        alerts,
        gene_results,
        expected_in_locus,
        expected_outside,
        other_in_locus,
        truncated,
        len_disc,
    )
