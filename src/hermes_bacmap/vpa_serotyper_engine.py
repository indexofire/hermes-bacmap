"""
Serotyping Engine - minimap2 + sourmash + gene-level verification.

Pipeline:
  A. minimap2: assembly contigs → ref_seqs.fasta → extract locus contigs
  B. sourmash: locus contigs vs reference sketches → best locus (containment)
  C. Gene-level: best locus genes → per-gene coverage/identity
  D. Decision: Typeable/Untypeable + Perfect/High/Medium/Low/Unknown
"""

from __future__ import annotations

import logging
import pickle
import hashlib
import hmac
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _locus_to_antigen(locus: str, prefix: str) -> str:
    if not locus or locus == "None":
        return f"{prefix}UT"
    if locus.startswith(f"{prefix}LU"):
        return f"{prefix}UT"
    m = re.match(rf"^{prefix}L(\d+)(?:V\d+)?$", locus)
    if m:
        return f"{prefix}{m.group(1)}"
    return f"{prefix}UT"


def _format_gene_details(genes: list[dict]) -> str:
    parts = []
    for g in genes:
        name = g.get("gene", "?")
        ident = g.get("identity", 0)
        cov = g.get("coverage", 0)
        status = g.get("status", "missing")
        parts.append(f"{name},{ident:.1f}%,{cov:.1f}%,{status}")
    return ";".join(parts) if parts else ""

SIGNING_KEY = b"vpautils-serotype-db-integrity"

MAX_GENE_DIFF = 4
MIN_CONTIG_ALIGN_LEN = 500
MIN_CONTAINMENT = 30.0
MIN_GENE_COV = 30.0
KMER_TIEBREAK_MARGIN = 5.0


class SerotyperEngine:

    ANTIGEN_BOUNDARY = {
        "O": {"start": "coaD", "end": "rfaD"},
        "K": {"start": "rfaD", "end": "glpX"},
    }

    def __init__(self, db_dir: Path, verbose: bool = False) -> None:
        self.db_dir = Path(db_dir)
        self.fasta_path = str(self.db_dir / "ref_seqs.fasta")
        self.gene_fasta_path = str(self.db_dir / "gene_refs.fasta")
        self.sketch_path = str(self.db_dir / "ref_sketches.sig")
        self.meta_path = self.db_dir / "ref_meta.pkl"
        self.sig_path = self.db_dir / "ref_meta.sig"
        self.verbose = verbose

        try:
            import mappy as mp
            self._mp = mp
        except ImportError:
            raise ImportError("mappy is required. Install: conda install -c bioconda minimap2")

        try:
            from sourmash import load_signatures
            self._load_signatures = load_signatures
        except ImportError:
            raise ImportError("sourmash is required. Install: pip install sourmash")

        if self.sig_path.exists():
            self._verify_signature()

        with open(self.meta_path, "rb") as f:
            loaded = pickle.load(f)
        self.metadata = loaded[0] if isinstance(loaded, tuple) else loaded

        self._build_gene_maps()
        self._load_sketches()

        logger.info(f"Loaded {len(self.metadata)} loci, {len(self.sketches)} sketches")
        self.locus_aligner = self._mp.Aligner(self.fasta_path, preset="splice")
        if not self.locus_aligner:
            raise RuntimeError("Failed to load minimap2 index.")

    def _build_gene_maps(self) -> None:
        self.locus_gene_names: dict[str, set[str]] = {}
        self.locus_type_map: dict[str, str] = {}
        for locus_id, meta in self.metadata.items():
            self.locus_gene_names[locus_id] = {g["locus_tag"] for g in meta["genes"]}
            self.locus_type_map[locus_id] = meta.get("type", "?")

    def _load_sketches(self) -> None:
        self.sketches: dict[str, Any] = {}
        self.sketch_mhs: dict[str, Any] = {}
        for sig in self._load_signatures(self.sketch_path):
            self.sketches[sig.name] = sig
            self.sketch_mhs[sig.name] = sig.minhash

    def _verify_signature(self) -> None:
        with open(self.meta_path, "rb") as f:
            loaded = pickle.load(f)
        if isinstance(loaded, tuple) and len(loaded) == 2:
            metadata, embedded_sig = loaded
            actual = hmac.new(SIGNING_KEY, pickle.dumps(metadata), hashlib.sha256).digest()
            if not hmac.compare_digest(actual, bytes(embedded_sig)):
                raise RuntimeError("Database signature verification failed.")

    def run_one_sample(self, sample_path: Path, enable_detail: bool = False,
                       min_containment: float = MIN_CONTAINMENT) -> dict[str, Any]:
        sample_name = Path(sample_path).stem

        try:
            sample_seqs = {}
            for name, seq, _ in self._mp.fastx_read(str(sample_path)):
                sample_seqs[name] = seq
        except Exception as e:
            return self._empty_result(sample_name, str(e))

        if not sample_seqs:
            return self._empty_result(sample_name)

        sample_aligner = self._mp.Aligner(str(sample_path), preset="splice")

        locus_contigs = self._extract_locus_contigs(sample_seqs)
        if not locus_contigs:
            return self._empty_result(sample_name)

        o_result = self._type_locus(locus_contigs, "O", sample_aligner, enable_detail, min_containment)
        k_result = self._type_locus(locus_contigs, "K", sample_aligner, enable_detail, min_containment)

        result = {"Sample": sample_name, "_gene_details": {"O": [], "K": []},
                  "_locus_pieces": {}, "_sample_seqs": sample_seqs}
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
                result[f"{ltype}_Genes_Detail"] = _format_gene_details(
                    typed.get("gene_details", [])
                )
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

    def _extract_locus_contigs(
        self, sample_seqs: dict[str, str]
    ) -> dict[str, list[tuple[str, str, int, int]]]:
        locus_contigs: dict[str, list[tuple[str, str, int, int]]] = defaultdict(list)
        seen: set[tuple[str, str, int, int]] = set()

        for contig_name, contig_seq in sample_seqs.items():
            for hit in self.locus_aligner.map(contig_seq):
                if hit.blen < MIN_CONTIG_ALIGN_LEN:
                    continue
                ref_name = hit.ctg
                locus_id = ref_name.split()[0] if " " in ref_name else ref_name
                if locus_id not in self.metadata:
                    continue
                key = (locus_id, contig_name, hit.q_st, hit.q_en)
                if key in seen:
                    continue
                seen.add(key)
                extracted = contig_seq[hit.q_st:hit.q_en]
                strand = int(hit.strand) if not isinstance(hit.strand, str) else (1 if hit.strand == "+" else -1)
                r_st = min(hit.r_st, hit.r_en)
                locus_contigs[locus_id].append((contig_name, extracted, strand, r_st))

        return dict(locus_contigs)

    def _type_locus(
        self,
        locus_contigs: dict[str, list[tuple[str, str, int, int]]],
        ltype: str,
        sample_aligner,
        enable_detail: bool = False,
        min_containment: float = MIN_CONTAINMENT,
    ) -> dict[str, Any] | None:
        type_contigs = {
            lid: entries for lid, entries in locus_contigs.items()
            if self.locus_type_map.get(lid) == ltype
        }
        if not type_contigs:
            return None

        ranked = self._rank_loci_by_kmer(type_contigs, ltype)
        if not ranked or ranked[0][1] < min_containment:
            result = {
                "locus": "None", "confidence": "Unknown",
                "coverage": 0, "identity": 0,
                "missing": "None", "alerts": "None",
                "gene_details": [],
                "expected_in_locus": "", "expected_in_locus_detail": "",
                "expected_outside": "", "expected_outside_detail": "",
                "other_in_locus": "0", "other_in_locus_detail": "",
                "truncated_detail": "", "length_discrepancy": "",
            }
            if enable_detail and ranked:
                result["detail_notes"] = (
                    f"No locus exceeded {min_containment:.0f}% containment threshold. "
                    f"Top candidate: {ranked[0][0]} ({ranked[0][1]:.1f}%). "
                    f"Likely a novel {ltype}-locus not in database."
                )
            else:
                result["detail_notes"] = ""
            return result

        best_locus = ranked[0][0]
        containment = ranked[0][1]
        valid_ids = {l for l, c in ranked if c >= min_containment}

        close = [(l, c) for l, c in ranked if c >= containment - KMER_TIEBREAK_MARGIN and c >= min_containment]
        if len(close) >= 2:
            best_locus = self._select_by_gene_coverage(
                [l for l, _ in close], type_contigs, sample_aligner
            )
            containment = dict(ranked)[best_locus]

        import re
        if re.search(r'V\d+$', best_locus):
            best_locus = self._resolve_variant_locus(
                best_locus, ltype, type_contigs, sample_aligner, valid_ids
            ) or best_locus

        superset = self._check_superset_override(
            best_locus, ltype, valid_ids, sample_aligner
        )
        if superset:
            best_locus = superset
            containment = dict(ranked).get(best_locus, containment)

        result = self._gene_level_analysis(best_locus, type_contigs, containment, sample_aligner)

        if enable_detail:
            result["detail_notes"] = self._generate_detail(
                ltype, best_locus, ranked, close, sample_aligner, result
            )
        else:
            result["detail_notes"] = ""

        return result

    def _identify_locus_by_kmer(
        self,
        type_contigs: dict[str, list],
        ltype: str,
    ) -> tuple[str | None, float]:
        ranked = self._rank_loci_by_kmer(type_contigs, ltype)
        if not ranked:
            return None, 0
        return ranked[0]

    def _rank_loci_by_kmer(
        self,
        type_contigs: dict[str, list],
        ltype: str,
    ) -> list[tuple[str, float]]:
        from sourmash import MinHash

        all_seqs = [entry[1] for entries in type_contigs.values() for entry in entries]
        if not all_seqs:
            return []

        sample_mh = MinHash(n=0, ksize=21, scaled=100)
        for seq in all_seqs:
            sample_mh.add_sequence(seq, force=True)

        scored = []
        for locus_id in self.sketch_mhs:
            if self.locus_type_map.get(locus_id) != ltype:
                continue
            ref_mh = self.sketch_mhs[locus_id]
            containment = ref_mh.contained_by(sample_mh) * 100
            scored.append((locus_id, containment))

        scored.sort(key=lambda x: -x[1])
        return scored

    def _select_by_gene_coverage(
        self,
        candidates: list[str],
        type_contigs: dict[str, list],
        sample_aligner,
    ) -> str:
        comp = str.maketrans("ATGCatgc", "TACGtacg")
        scores: dict[str, tuple[float, float]] = {}

        for lid in candidates:
            meta = self.metadata.get(lid)
            if not meta:
                continue

            locus_seq = None
            for name, seq, _ in self._mp.fastx_read(self.fasta_path):
                if name.split()[0] == lid:
                    locus_seq = seq
                    break

            if not locus_seq:
                continue

            present = 0
            total_ident = 0.0
            total_genes = len(meta["genes"])

            for gene in meta["genes"]:
                g_seq = locus_seq[gene["start"]:gene["end"]]
                if gene.get("strand", 1) == -1:
                    g_seq = g_seq[::-1].translate(comp)

                best_cov = best_ident = 0.0
                for h in sample_aligner.map(g_seq):
                    cov = 100.0 * h.blen / len(g_seq) if g_seq else 0
                    if cov > best_cov:
                        best_cov = cov
                        best_ident = 100.0 * h.mlen / h.blen if h.blen else 0

                if best_cov >= MIN_GENE_COV:
                    present += 1
                    total_ident += best_ident

            gene_cov = present / total_genes * 100 if total_genes else 0
            avg_ident = total_ident / present if present else 0
            scores[lid] = (gene_cov, present, avg_ident)

            logger.debug(f"  Gene tiebreak: {lid} = {present}/{total_genes} ({gene_cov:.1f}%) ident={avg_ident:.1f}%")

        if not scores:
            return candidates[0]

        return max(scores, key=lambda x: (scores[x][0], scores[x][1], scores[x][2]))

    def _check_superset_override(
        self,
        best_locus: str,
        ltype: str,
        valid_ids: set[str],
        sample_aligner,
    ) -> str | None:
        best_genes = self.metadata.get(best_locus, {}).get("genes", [])
        if not best_genes:
            return None

        candidates = [
            lid for lid in valid_ids
            if lid != best_locus
            and self.locus_type_map.get(lid) == ltype
            and len(self.metadata.get(lid, {}).get("genes", [])) > len(best_genes)
        ]
        if not candidates:
            return None

        comp = str.maketrans("ATGCatgc", "TACGtacg")
        needed = set(candidates) | {best_locus}
        seqs: dict[str, str] = {}
        for name, seq, _ in self._mp.fastx_read(self.fasta_path):
            lid = name.split()[0] if " " in name else name
            if lid in needed:
                seqs[lid] = seq
                needed.discard(lid)
                if not needed:
                    break

        best_seq = seqs.get(best_locus, "")
        if not best_seq:
            return None

        best_aligner = self._mp.Aligner(seq=best_seq, preset="splice")

        def present_genes_in_sample(ref_seq):
            present = set()
            for i, g in enumerate(self.metadata.get(best_locus, {}).get("genes", [])):
                gseq = ref_seq[g["start"]:g["end"]]
                if g.get("strand", 1) == -1:
                    gseq = gseq[::-1].translate(comp)
                for h in sample_aligner.map(gseq):
                    if 100.0 * h.blen / len(gseq) >= 30.0:
                        present.add(i)
                        break
            return present

        present_indices = present_genes_in_sample(best_seq)

        def present_genes_are_subset(aligner_b):
            for i in present_indices:
                g = self.metadata[best_locus]["genes"][i]
                gseq = best_seq[g["start"]:g["end"]]
                if g.get("strand", 1) == -1:
                    gseq = gseq[::-1].translate(comp)
                has_match = False
                for h in aligner_b.map(gseq):
                    if 100.0 * h.blen / len(gseq) >= 30.0:
                        has_match = True
                        break
                if not has_match:
                    return False
            return True

        for lid in candidates:
            cand_seq = seqs.get(lid, "")
            if not cand_seq:
                continue

            cand_aligner = self._mp.Aligner(seq=cand_seq, preset="splice")

            if not present_genes_are_subset(cand_aligner):
                continue

            cand_unique_present = 0
            cand_unique_total = 0
            for g in self.metadata[lid]["genes"]:
                gseq = cand_seq[g["start"]:g["end"]]
                if g.get("strand", 1) == -1:
                    gseq = gseq[::-1].translate(comp)
                is_unique = True
                for h in best_aligner.map(gseq):
                    if 100.0 * h.blen / len(gseq) >= 30.0:
                        is_unique = False
                        break
                if not is_unique:
                    continue

                cand_unique_total += 1
                for h in sample_aligner.map(gseq):
                    if 100.0 * h.blen / len(gseq) >= 80.0:
                        cand_unique_present += 1
                        break

            if cand_unique_total > 0 and cand_unique_present >= cand_unique_total * 0.5:
                logger.debug(
                    f"  Superset override: {best_locus} is subset of {lid}, "
                    f"{lid} unique genes {cand_unique_present}/{cand_unique_total} present -> switch to {lid}"
                )
                return lid

        return None

    def _generate_detail(
        self, ltype, best_locus, ranked, close, sample_aligner, result
    ) -> str:
        comp = str.maketrans("ATGCatgc", "TACGtacg")
        confidence = result.get("confidence", "Unknown")

        if confidence in ("Perfect",) and not close:
            return ""

        parts = []

        if len(close) >= 2:
            close_ids = [l for l, _ in close[:5]]
            parts.append(
                f"{len(close)} candidates within {KMER_TIEBREAK_MARGIN:.0f}% k-mer: "
                + ", ".join(f"{l}({c:.1f}%)" for l, c in close[:5])
            )

            seq_cache: dict[str, str] = {}
            needed = set(close_ids)
            for name, seq, _ in self._mp.fastx_read(self.fasta_path):
                lid = name.split()[0] if " " in name else name
                if lid in needed:
                    seq_cache[lid] = seq
                    needed.discard(lid)
                    if not needed:
                        break

            for lid in close_ids[:4]:
                if lid == best_locus or lid not in seq_cache:
                    continue
                uniq_present, uniq_total = self._count_unique_genes(
                    lid, best_locus, seq_cache, sample_aligner, comp
                )
                rev_uniq_p, rev_uniq_t = self._count_unique_genes(
                    best_locus, lid, seq_cache, sample_aligner, comp
                )
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

    def _count_unique_genes(self, lid_a, lid_b, seq_cache, sample_aligner, comp):
        genes_a = self.metadata.get(lid_a, {}).get("genes", [])
        seq_a = seq_cache.get(lid_a, "")
        seq_b = seq_cache.get(lid_b, "")
        if not seq_a or not seq_b:
            return 0, 0

        aln_b = self._mp.Aligner(seq=seq_b, preset="splice")
        unique = []
        for g in genes_a:
            gseq = seq_a[g["start"]:g["end"]]
            if g.get("strand", 1) == -1:
                gseq = gseq[::-1].translate(comp)
            is_unique = True
            for h in aln_b.map(gseq):
                if 100.0 * h.blen / len(gseq) >= 30.0:
                    is_unique = False
                    break
            if is_unique:
                unique.append(gseq)

        present = 0
        for gseq in unique:
            for h in sample_aligner.map(gseq):
                if 100.0 * h.blen / len(gseq) >= 80.0:
                    present += 1
                    break

        return present, len(unique)

    def _resolve_variant_locus(
        self,
        best_locus: str,
        ltype: str,
        type_contigs: dict[str, list[tuple[str, str]]],
        sample_aligner,
        valid_ids: set[str] | None = None,
    ) -> str | None:
        """Resolve OLnVn locus by checking presence of locus-unique genes only."""
        import re

        m = re.match(r'^(.+?)V\d+$', best_locus)
        if not m:
            return None
        base = m.group(1)

        candidates = [
            lid for lid in self.metadata
            if self.locus_type_map.get(lid) == ltype
            and (lid == base or re.match(rf'^{re.escape(base)}V\d+$', lid))
            and (valid_ids is None or lid in valid_ids)
        ]
        if len(candidates) < 2:
            return None

        comp = str.maketrans("ATGCatgc", "TACGtacg")
        locus_seqs: dict[str, str] = {}
        for name, seq, _ in self._mp.fastx_read(self.fasta_path):
            lid = name.split()[0] if " " in name else name
            if lid in candidates:
                locus_seqs[lid] = seq

        locus_aligners = {
            lid: self._mp.Aligner(seq=seq, preset="splice")
            for lid, seq in locus_seqs.items()
        }

        def extract_gene_seq(lid, gene):
            gseq = locus_seqs[lid][gene["start"]:gene["end"]]
            if gene.get("strand", 1) == -1:
                gseq = gseq[::-1].translate(comp)
            return gseq

        def sample_identity(g_seq):
            best = 0.0
            for h in sample_aligner.map(g_seq):
                cov = 100.0 * h.blen / len(g_seq) if g_seq else 0
                if cov >= MIN_GENE_COV:
                    ident = 100.0 * h.mlen / h.blen if h.blen else 0
                    if ident > best:
                        best = ident
            return best

        def is_unique(g_seq, other_lids):
            for olid in other_lids:
                for h in locus_aligners[olid].map(g_seq):
                    cov = 100.0 * h.blen / len(g_seq) if g_seq else 0
                    if cov >= 30.0:
                        return False
            return True

        votes: dict[str, int] = {lid: 0 for lid in candidates}
        vote_log: list[str] = []

        for lid_a in candidates:
            other_lids = [l for l in candidates if l != lid_a]
            for gene in self.metadata[lid_a]["genes"]:
                g_seq = extract_gene_seq(lid_a, gene)
                if not is_unique(g_seq, other_lids):
                    continue

                si = sample_identity(g_seq)
                if si >= 80.0:
                    votes[lid_a] += 1
                    vote_log.append(f"{gene['name']}({lid_a}): unique, sample={si:.1f}% -> +{lid_a}")

        for line in vote_log:
            logger.debug(f"  Vote: {line}")
        for lid in candidates:
            logger.debug(f"  {lid}: {votes[lid]} votes")

        best_lid = max(votes, key=votes.get)
        tied = [lid for lid in candidates if lid != best_lid and votes[lid] == votes[best_lid]]
        if tied:
            logger.debug("  -> TIE, keeping k-mer result")
            return None

        if votes[best_lid] == 0:
            return None

        logger.debug(f"  -> Winner: {best_lid}")
        return best_lid

    def _gene_level_analysis(
        self,
        best_locus: str,
        type_contigs: dict[str, list[tuple[str, str]]],
        containment: float,
        sample_aligner,
    ) -> dict[str, Any]:
        meta = self.metadata[best_locus]
        comp = str.maketrans("ATGCatgc", "TACGtacg")
        ltype = meta.get("type", "?")

        locus_seq = None
        for name, seq, _ in self._mp.fastx_read(self.fasta_path):
            if name.split()[0] == best_locus:
                locus_seq = seq
                break

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
            g_start, g_end = gene["start"], gene["end"]

            if not locus_seq:
                missing_genes.append(g_name)
                gene_results.append({"gene": g_name, "identity": 0, "coverage": 0, "status": "missing"})
                continue

            g_seq = locus_seq[g_start:g_end]
            if gene.get("strand", 1) == -1:
                g_seq = g_seq[::-1].translate(comp)

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
                    "gene": g_name, "identity": round(best_ident, 2),
                    "coverage": round(best_cov, 2), "status": "present",
                    "ctg": best_ctg, "r_st": best_r_st, "r_en": best_r_en,
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
            for g in gene_results if g["status"] == "present" and g.get("ctg")
        ]

        locus_region_aligner = self._build_locus_region_aligner(
            type_contigs.get(best_locus, [])
        )

        other_in_locus = self._find_other_genes_in_locus(
            best_locus, ltype, locus_region_aligner, occupied_regions, sample_aligner
        )

        boundary = self.ANTIGEN_BOUNDARY.get(ltype, {})
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

        typeable, confidence = self._decide(
            gene_diff, gene_coverage, identity, pieces, missing_boundary
        )

        alerts = []
        if pieces > 1:
            alerts.append("Fragmented")
        if missing_boundary:
            alerts.append(f"MissingBoundary({','.join(missing_boundary)})")

        total_genes = len(gene_results)
        return {
            "locus": best_locus,
            "confidence": confidence,
            "coverage": round(gene_coverage, 2),
            "identity": round(identity, 2),
            "missing": ";".join(missing_genes) if missing_genes else "None",
            "alerts": ";".join(alerts) if alerts else "None",
            "gene_details": gene_results,
            "expected_in_locus": f"{len(expected_in_locus)} / {total_genes} ({len(expected_in_locus)/total_genes*100:.2f}%)" if total_genes else "0 / 0",
            "expected_in_locus_detail": ";".join(expected_in_locus),
            "expected_outside": f"{len(expected_outside)} / {total_genes} ({len(expected_outside)/total_genes*100:.2f}%)" if total_genes else "0 / 0",
            "expected_outside_detail": ";".join(expected_outside),
            "other_in_locus": str(len(other_in_locus)),
            "other_in_locus_detail": ";".join(other_in_locus),
            "truncated_detail": ";".join(truncated),
            "length_discrepancy": f"{len_disc} bp",
        }

    def _build_locus_region_aligner(self, entries: list[tuple[str, str]]):
        if not entries:
            return None
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix=".fasta", delete=False, mode="w")
        for i, entry in enumerate(entries):
            tmp.write(f">region_{i}\n{entry[1]}\n")
        tmp.close()
        aligner = self._mp.Aligner(tmp.name, preset="splice")
        os.unlink(tmp.name)
        return aligner

    def _find_other_genes_in_locus(
        self,
        best_locus: str,
        ltype: str,
        locus_region_aligner,
        occupied_regions: list[tuple[str, int, int]],
        sample_aligner,
    ) -> list[str]:
        if not locus_region_aligner:
            return []

        comp = str.maketrans("ATGCatgc", "TACGtacg")
        other_loci = [
            lid for lid in self.metadata
            if self.locus_type_map.get(lid) == ltype and lid != best_locus
        ]

        all_seqs_cache: dict[str, str] = {}
        for name, seq, _ in self._mp.fastx_read(self.fasta_path):
            lid = name.split()[0] if " " in name else name
            if lid in other_loci or lid == best_locus:
                all_seqs_cache[lid] = seq

        if best_locus not in all_seqs_cache:
            for name, seq, _ in self._mp.fastx_read(self.fasta_path):
                if name.split()[0] == best_locus:
                    all_seqs_cache[best_locus] = seq
                    break

        best_seq = all_seqs_cache.get(best_locus, "")

        best_aligner = None
        if best_seq:
            best_aligner = self._mp.Aligner(seq=best_seq, preset="splice")

        def has_match_in_best_locus(g_seq):
            if not best_aligner:
                return False
            for h in best_aligner.map(g_seq):
                cov = 100.0 * h.blen / len(g_seq) if g_seq else 0
                if cov >= 30.0:
                    return True
            return False

        results = []
        seen_genes: set[str] = set()
        for lid in other_loci:
            lseq = all_seqs_cache.get(lid)
            if not lseq:
                continue
            for gene in self.metadata[lid]["genes"]:
                gname = gene.get("locus_tag", gene["name"])
                if gname in seen_genes:
                    continue
                g_seq = lseq[gene["start"]:gene["end"]]
                if gene.get("strand", 1) == -1:
                    g_seq = g_seq[::-1].translate(comp)
                if not g_seq:
                    continue

                if has_match_in_best_locus(g_seq):
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

    def _decide(
        self, gene_diff: int, gene_coverage: float, identity: float,
        pieces: int, missing_boundary: list[str],
    ) -> tuple[bool, str]:
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

    def _empty_result(self, sample_name: str, error: str = "") -> dict[str, Any]:
        result = {"Sample": sample_name, "_gene_details": {"O": [], "K": []}}
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

    def get_reference_genes(self, locus_id: str) -> list[dict]:
        if locus_id not in self.metadata:
            return []
        return [
            {
                "locus_tag": g.get("locus_tag", g["name"]),
                "name": g["name"],
                "product": g.get("product", ""),
                "start": g["start"],
                "end": g["end"],
                "strand": g.get("strand", 1),
            }
            for g in self.metadata[locus_id]["genes"]
        ]
