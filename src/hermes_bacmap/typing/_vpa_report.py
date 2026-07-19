"""Report assembly for the VPA serotyper (result dicts and detail notes)."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from ._vpa_kmer import KMER_TIEBREAK_MARGIN


def _locus_to_antigen(locus: str, prefix: str) -> str:
    if not locus or locus == "None":
        return f"{prefix}UT"
    if locus.startswith(f"{prefix}LU"):
        return f"{prefix}UT"
    m = re.match(rf"^{prefix}L(\d+)(?:V\d+)?$", locus)
    if m:
        return f"{prefix}{m.group(1)}"
    return f"{prefix}UT"


def format_gene_details(genes: list[dict[str, Any]]) -> str:
    """Format per-gene entries as 'name,ident%,cov%,status' joined by ';'."""
    parts = []
    for g in genes:
        name = g.get("gene", "?")
        ident = g.get("identity", 0)
        cov = g.get("coverage", 0)
        status = g.get("status", "missing")
        parts.append(f"{name},{ident:.1f}%,{cov:.1f}%,{status}")
    return ";".join(parts) if parts else ""


def empty_result(sample_name: str, error: str = "") -> dict[str, Any]:
    """Build the all-unknown result dict for an untypeable or failed sample."""
    result: dict[str, Any] = {"Sample": sample_name, "_gene_details": {"O": [], "K": []}}
    for lt in ("O", "K"):
        result[f"{lt}_Locus"] = "None"
        result[f"{lt}_Confidence"] = "Unknown"
        result[f"{lt}_Coverage"] = 0
        result[f"{lt}_Identity"] = 0
        result[f"{lt}_Missing_Genes"] = error or "No match"
        result[f"{lt}_Alerts"] = "None"
        result[f"{lt}_Genes_Detail"] = ""
        result[f"{lt}_Expected_In_Locus"] = ""
        result[f"{lt}_Expected_In_Locus_Detail"] = ""
        result[f"{lt}_Expected_Outside"] = ""
        result[f"{lt}_Expected_Outside_Detail"] = ""
        result[f"{lt}_Other_In_Locus"] = "0"
        result[f"{lt}_Other_In_Locus_Detail"] = ""
        result[f"{lt}_Truncated"] = ""
        result[f"{lt}_Length_Discrepancy"] = ""
    result["Predicted_Serotype"] = "OUT:KUT"
    return result


def assemble_sample_result(
    sample_name: str,
    sample_seqs: dict[str, str],
    locus_contigs: dict[str, list[tuple[str, str, int, int]]],
    o_result: dict[str, Any] | None,
    k_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble the full per-sample report dict from the O/K locus typing results."""
    result: dict[str, Any] = {
        "Sample": sample_name,
        "_gene_details": {"O": [], "K": []},
        "_locus_pieces": {},
        "_sample_seqs": sample_seqs,
    }
    for ltype, typed in [("O", o_result), ("K", k_result)]:
        locus_name = typed["locus"] if typed else "None"
        if typed and locus_name != "None":
            result["_locus_pieces"][ltype] = locus_contigs.get(locus_name, [])
        else:
            result["_locus_pieces"][ltype] = []
    for ltype, typed in [("O", o_result), ("K", k_result)]:
        if typed:
            result[f"{ltype}_Locus"] = typed["locus"]
            result[f"{ltype}_Confidence"] = typed["confidence"]
            result[f"{ltype}_Coverage"] = typed["coverage"]
            result[f"{ltype}_Identity"] = typed["identity"]
            result[f"{ltype}_Missing_Genes"] = typed["missing"]
            result[f"{ltype}_Alerts"] = typed["alerts"]
            result[f"{ltype}_Genes_Detail"] = format_gene_details(typed.get("gene_details", []))
            result[f"{ltype}_Expected_In_Locus"] = typed.get("expected_in_locus", "")
            result[f"{ltype}_Expected_In_Locus_Detail"] = typed.get("expected_in_locus_detail", "")
            result[f"{ltype}_Expected_Outside"] = typed.get("expected_outside", "")
            result[f"{ltype}_Expected_Outside_Detail"] = typed.get("expected_outside_detail", "")
            result[f"{ltype}_Other_In_Locus"] = typed.get("other_in_locus", "0")
            result[f"{ltype}_Other_In_Locus_Detail"] = typed.get("other_in_locus_detail", "")
            result[f"{ltype}_Truncated"] = typed.get("truncated_detail", "")
            result[f"{ltype}_Length_Discrepancy"] = typed.get("length_discrepancy", "")
            result[f"{ltype}_Detail"] = typed.get("detail_notes", "")
            result["_gene_details"][ltype] = typed.get("gene_details", [])
        else:
            result[f"{ltype}_Locus"] = "None"
            result[f"{ltype}_Confidence"] = "Unknown"
            result[f"{ltype}_Coverage"] = 0
            result[f"{ltype}_Identity"] = 0
            result[f"{ltype}_Missing_Genes"] = "None"
            result[f"{ltype}_Alerts"] = "None"
            result[f"{ltype}_Genes_Detail"] = ""
            result[f"{ltype}_Expected_In_Locus"] = ""
            result[f"{ltype}_Expected_In_Locus_Detail"] = ""
            result[f"{ltype}_Expected_Outside"] = ""
            result[f"{ltype}_Expected_Outside_Detail"] = ""
            result[f"{ltype}_Other_In_Locus"] = "0"
            result[f"{ltype}_Other_In_Locus_Detail"] = ""
            result[f"{ltype}_Truncated"] = ""
            result[f"{ltype}_Length_Discrepancy"] = ""
            result[f"{ltype}_Detail"] = ""

    o_ag = _locus_to_antigen(result["O_Locus"], "O")
    k_ag = _locus_to_antigen(result["K_Locus"], "K")
    result["Predicted_Serotype"] = f"{o_ag}:{k_ag}"
    return result


def build_gene_result(
    best_locus: str,
    confidence: str,
    gene_coverage: float,
    identity: float,
    missing_genes: list[str],
    alerts: list[str],
    gene_results: list[dict[str, Any]],
    expected_in_locus: list[str],
    expected_outside: list[str],
    other_in_locus: list[str],
    truncated: list[str],
    len_disc: int,
) -> dict[str, Any]:
    """Assemble the per-locus gene-level analysis result dict."""
    total_genes = len(gene_results)
    return {
        "locus": best_locus,
        "confidence": confidence,
        "coverage": round(gene_coverage, 2),
        "identity": round(identity, 2),
        "missing": ";".join(missing_genes) if missing_genes else "None",
        "alerts": ";".join(alerts) if alerts else "None",
        "gene_details": gene_results,
        "expected_in_locus": (
            f"{len(expected_in_locus)} / {total_genes}"
            f" ({len(expected_in_locus) / total_genes * 100:.2f}%)"
            if total_genes
            else "0 / 0"
        ),
        "expected_in_locus_detail": ";".join(expected_in_locus),
        "expected_outside": (
            f"{len(expected_outside)} / {total_genes}"
            f" ({len(expected_outside) / total_genes * 100:.2f}%)"
            if total_genes
            else "0 / 0"
        ),
        "expected_outside_detail": ";".join(expected_outside),
        "other_in_locus": str(len(other_in_locus)),
        "other_in_locus_detail": ";".join(other_in_locus),
        "truncated_detail": ";".join(truncated),
        "length_discrepancy": f"{len_disc} bp",
    }


def generate_detail(
    ltype: str,
    best_locus: str,
    ranked: list[tuple[str, float]],
    close: list[tuple[str, float]],
    sample_aligner: Any,
    result: dict[str, Any],
    *,
    ref_fasta: Any,
    count_unique: Callable[..., tuple[int, int]],
) -> str:
    """Build detail notes for a typed locus (close candidates / untypeable explanation)."""
    comp = str.maketrans("ATGCatgc", "TACGtacg")
    confidence = result.get("confidence", "Unknown")

    if confidence in ("Perfect",) and not close:
        return ""

    parts = []

    if len(close) >= 2:
        close_ids = [loc for loc, _ in close[:5]]
        parts.append(
            f"{len(close)} candidates within {KMER_TIEBREAK_MARGIN:.0f}% k-mer: "
            + ", ".join(f"{loc}({c:.1f}%)" for loc, c in close[:5])
        )

        seq_cache: dict[str, str] = ref_fasta.all()

        for lid in close_ids[:4]:
            if lid == best_locus or lid not in seq_cache:
                continue
            uniq_present, uniq_total = count_unique(
                lid, best_locus, seq_cache, sample_aligner, comp
            )
            rev_uniq_p, rev_uniq_t = count_unique(best_locus, lid, seq_cache, sample_aligner, comp)
            parts.append(
                f"  {best_locus} unique: {rev_uniq_p}/{rev_uniq_t} present; "
                f"{lid} unique: {uniq_present}/{uniq_total} present"
            )

            if rev_uniq_t > 0 and rev_uniq_p == 0 and uniq_total > 0 and uniq_present == 0:
                parts.append(
                    f"  -> Neither {best_locus} nor {lid} unique genes detected. "
                    f"Likely a novel {ltype}-locus sharing framework genes."
                )
            elif uniq_total > 0 and uniq_present > 0 and rev_uniq_p == 0:
                parts.append(
                    f"  -> Caution: {lid} unique genes detected but {best_locus} was selected."
                )

    if confidence == "Unknown" and result.get("locus", "None") != "None":
        gene_diff = result.get("missing", "")
        n_missing = len(gene_diff.split(";")) if gene_diff and gene_diff != "None" else 0
        parts.append(
            f"Untypeable: {n_missing} genes missing from {result['locus']} "
            f"(coverage={result['coverage']:.1f}%, identity={result['identity']:.1f}%)."
        )
        if not close or len(close) < 2:
            parts.append(
                f"No close competitor within {KMER_TIEBREAK_MARGIN:.0f}% k-mer margin. "
                f"Sample may have recombination or partial locus deletion."
            )

    return " ".join(parts) if parts else ""
