"""
Serotyping Engine - minimap2 + sourmash + gene-level verification.

Pipeline:
  A. minimap2: assembly contigs → ref_seqs.fasta → extract locus contigs
  B. sourmash: locus contigs vs reference sketches → best locus (containment)
  C. Gene-level: best locus genes → per-gene coverage/identity
  D. Decision: Typeable/Untypeable + Perfect/High/Medium/Low/Unknown

Orchestration facade: k-mer ranking lives in `_vpa_kmer`, gene-level
verification in `_vpa_genes`, and report assembly in `_vpa_report`.
"""

from __future__ import annotations

import functools
import hashlib
import hmac
import logging
import pickle
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import _vpa_genes, _vpa_kmer, _vpa_report
from ._vpa_genes import MAX_GENE_DIFF, MIN_CONTIG_ALIGN_LEN, MIN_GENE_COV
from ._vpa_kmer import KMER_TIEBREAK_MARGIN, MIN_CONTAINMENT
from ._vpa_report import _locus_to_antigen
from ._vpa_report import format_gene_details as _format_gene_details

logger = logging.getLogger(__name__)

__all__ = [
    "KMER_TIEBREAK_MARGIN",
    "MAX_GENE_DIFF",
    "MIN_CONTAINMENT",
    "MIN_CONTIG_ALIGN_LEN",
    "MIN_GENE_COV",
    "SIGNING_KEY",
    "SerotyperEngine",
    "_format_gene_details",
    "_locus_to_antigen",
]

SIGNING_KEY = b"vpautils-serotype-db-integrity"


class SerotyperEngine:
    ANTIGEN_BOUNDARY = _vpa_genes.ANTIGEN_BOUNDARY

    # Class-level defaults so methods can run on __new__-constructed instances.
    _mp: Any = None
    _ref_fasta: Any = None

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
        self._ref_fasta = _vpa_genes._RefFasta(self._mp, self.fasta_path)

    def _build_gene_maps(self) -> None:
        self.locus_type_map: dict[str, str] = {}
        for locus_id, meta in self.metadata.items():
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

    def run_one_sample(
        self,
        sample_path: Path,
        enable_detail: bool = False,
        min_containment: float = MIN_CONTAINMENT,
    ) -> dict[str, Any]:
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

        o_result = self._type_locus(
            locus_contigs, "O", sample_aligner, enable_detail, min_containment
        )
        k_result = self._type_locus(
            locus_contigs, "K", sample_aligner, enable_detail, min_containment
        )

        return _vpa_report.assemble_sample_result(
            sample_name, sample_seqs, locus_contigs, o_result, k_result
        )

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
                extracted = contig_seq[hit.q_st : hit.q_en]
                strand = (
                    int(hit.strand)
                    if not isinstance(hit.strand, str)
                    else (1 if hit.strand == "+" else -1)
                )
                r_st = min(hit.r_st, hit.r_en)
                locus_contigs[locus_id].append((contig_name, extracted, strand, r_st))

        return dict(locus_contigs)

    def _type_locus(
        self,
        locus_contigs: dict[str, list[tuple[str, str, int, int]]],
        ltype: str,
        sample_aligner: Any,
        enable_detail: bool = False,
        min_containment: float = MIN_CONTAINMENT,
    ) -> dict[str, Any] | None:
        type_contigs = {
            lid: entries
            for lid, entries in locus_contigs.items()
            if self.locus_type_map.get(lid) == ltype
        }
        if not type_contigs:
            return None

        ranked = self._rank_loci_by_kmer(type_contigs, ltype)
        if not ranked or ranked[0][1] < min_containment:
            result = {
                "locus": "None",
                "confidence": "Unknown",
                "coverage": 0,
                "identity": 0,
                "missing": "None",
                "alerts": "None",
                "gene_details": [],
                "expected_in_locus": "",
                "expected_in_locus_detail": "",
                "expected_outside": "",
                "expected_outside_detail": "",
                "other_in_locus": "0",
                "other_in_locus_detail": "",
                "truncated_detail": "",
                "length_discrepancy": "",
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
        valid_ids = {loc for loc, c in ranked if c >= min_containment}

        close = [
            (loc, c)
            for loc, c in ranked
            if c >= containment - KMER_TIEBREAK_MARGIN and c >= min_containment
        ]
        if len(close) >= 2:
            best_locus = self._select_by_gene_coverage(
                [loc for loc, _ in close], type_contigs, sample_aligner
            )
            containment = dict(ranked)[best_locus]

        if re.search(r"V\d+$", best_locus):
            best_locus = (
                self._resolve_variant_locus(
                    best_locus, ltype, type_contigs, sample_aligner, valid_ids
                )
                or best_locus
            )

        superset = self._check_superset_override(best_locus, ltype, valid_ids, sample_aligner)
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
        type_contigs: dict[str, list[tuple[str, str, int, int]]],
        ltype: str,
    ) -> tuple[str | None, float]:
        return _vpa_kmer.identify_locus_by_kmer(
            self.sketch_mhs, self.locus_type_map, type_contigs, ltype
        )

    def _rank_loci_by_kmer(
        self,
        type_contigs: dict[str, list[tuple[str, str, int, int]]],
        ltype: str,
    ) -> list[tuple[str, float]]:
        return _vpa_kmer.rank_loci_by_kmer(
            self.sketch_mhs, self.locus_type_map, type_contigs, ltype
        )

    def _select_by_gene_coverage(
        self,
        candidates: list[str],
        type_contigs: dict[str, list[tuple[str, str, int, int]]],
        sample_aligner: Any,
    ) -> str:
        return _vpa_genes.select_by_gene_coverage(
            self._mp, self.metadata, self._ref_fasta, candidates, sample_aligner
        )

    def _check_superset_override(
        self,
        best_locus: str,
        ltype: str,
        valid_ids: set[str],
        sample_aligner: Any,
    ) -> str | None:
        return _vpa_genes.check_superset_override(
            self._mp,
            self.metadata,
            getattr(self, "locus_type_map", {}),
            self._ref_fasta,
            best_locus,
            ltype,
            valid_ids,
            sample_aligner,
        )

    def _generate_detail(
        self,
        ltype: str,
        best_locus: str,
        ranked: list[tuple[str, float]],
        close: list[tuple[str, float]],
        sample_aligner: Any,
        result: dict[str, Any],
    ) -> str:
        return _vpa_report.generate_detail(
            ltype,
            best_locus,
            ranked,
            close,
            sample_aligner,
            result,
            ref_fasta=self._ref_fasta,
            count_unique=functools.partial(_vpa_genes.count_unique_genes, self._mp, self.metadata),
        )

    def _count_unique_genes(
        self,
        lid_a: str,
        lid_b: str,
        seq_cache: dict[str, str],
        sample_aligner: Any,
        comp: dict[int, int],
    ) -> tuple[int, int]:
        return _vpa_genes.count_unique_genes(
            self._mp, self.metadata, lid_a, lid_b, seq_cache, sample_aligner, comp
        )

    def _resolve_variant_locus(
        self,
        best_locus: str,
        ltype: str,
        type_contigs: dict[str, list[tuple[str, str, int, int]]],
        sample_aligner: Any,
        valid_ids: set[str] | None = None,
    ) -> str | None:
        """Resolve OLnVn locus by checking presence of locus-unique genes only."""
        return _vpa_genes.resolve_variant_locus(
            self._mp,
            self.metadata,
            getattr(self, "locus_type_map", {}),
            self._ref_fasta,
            best_locus,
            ltype,
            type_contigs,
            sample_aligner,
            valid_ids,
        )

    def _gene_level_analysis(
        self,
        best_locus: str,
        type_contigs: dict[str, list[tuple[str, str, int, int]]],
        containment: float,
        sample_aligner: Any,
    ) -> dict[str, Any]:
        return _vpa_genes.gene_level_analysis(
            self._mp,
            self.metadata,
            getattr(self, "locus_type_map", {}),
            self._ref_fasta,
            best_locus,
            type_contigs,
            containment,
            sample_aligner,
        )

    def _build_locus_region_aligner(self, entries: list[tuple[str, str, int, int]]) -> Any:
        return _vpa_genes.build_locus_region_aligner(self._mp, entries)

    def _find_other_genes_in_locus(
        self,
        best_locus: str,
        ltype: str,
        locus_region_aligner: Any,
        occupied_regions: list[tuple[str, int, int]],
        sample_aligner: Any,
    ) -> list[str]:
        return _vpa_genes.find_other_genes_in_locus(
            self._mp,
            self.metadata,
            getattr(self, "locus_type_map", {}),
            self._ref_fasta,
            best_locus,
            ltype,
            locus_region_aligner,
            occupied_regions,
            sample_aligner,
        )

    def _decide(
        self,
        gene_diff: int,
        gene_coverage: float,
        identity: float,
        pieces: int,
        missing_boundary: list[str],
    ) -> tuple[bool, str]:
        return _vpa_genes.decide(gene_diff, gene_coverage, identity, pieces, missing_boundary)

    def _empty_result(self, sample_name: str, error: str = "") -> dict[str, Any]:
        return _vpa_report.empty_result(sample_name, error)

    def get_reference_genes(self, locus_id: str) -> list[dict[str, Any]]:
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
