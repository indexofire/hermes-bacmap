"""Engine — unified sequence operations abstraction layer.

Decouples pipeline logic from specific CLI tools (blastn, minimap2, bwa).
Provides SequenceMatcher and ReadMapper facades with auto backend selection.

Usage:
    from hermes_bacmap.engine import SequenceMatcher

    hits = SequenceMatcher.match(
        query="contigs.fasta",
        db_prefix="data/reference/card",
        mode="blastn",
    )
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .hits import Hit
from .backends import get_backend, available
from .utils import merge_intervals, confidence_tier, classify_allele
from .registry import Registry
from .read_mapper import ReadMapper

__all__ = [
    "Hit",
    "SequenceMatcher",
    "ReadMapper",
    "available",
    "merge_intervals",
    "confidence_tier",
    "classify_allele",
]


class SequenceMatcher:
    """Unified sequence matching with auto backend selection."""

    @classmethod
    def match(
        cls,
        query: str | Path,
        db_prefix: str = "",
        db_path: str = "",
        mode: str = "auto",
        query_type: str = "auto",
        min_identity: float = 0.0,
        min_coverage: float = 0.0,
        **kwargs: Any,
    ) -> list[Hit]:
        target = db_prefix or db_path

        if mode == "auto":
            mode = cls._select_backend(query, query_type)

        if mode in ("blastp", "blastx", "tblastn"):
            backend = get_backend(mode, tool=mode)
        else:
            backend = get_backend(mode)

        if mode == "minimap2":
            return backend.find(
                query=Path(query),
                target=Path(target),
                min_identity=min_identity,
                min_coverage=min_coverage,
                **kwargs,
            )

        return backend.find(
            query=Path(query),
            db_path=target,
            min_identity=min_identity,
            min_coverage=min_coverage,
            **kwargs,
        )

    @staticmethod
    def _select_backend(query: str | Path, query_type: str) -> str:
        if query_type == "prot":
            return "blastp"

        query_size = Path(query).stat().st_size if Path(query).exists() else 0
        if query_size > 10_000_000:
            return "minimap2"

        return "blastn"
