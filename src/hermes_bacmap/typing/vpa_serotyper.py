"""V. parahaemolyticus O/K serotyping — ported from vpautils.

Wraps SerotyperEngine (minimap2 + sourmash + gene-level verification)
for the hermes-bacmap pipeline.

Usage:
    from hermes_bacmap.typing.vpa_serotyper import VpaSerotyper
    serotyper = VpaSerotyper()
    result = serotyper.analyze("results/SAM-XXX/assembly/contigs.fasta")
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermes_bacmap.config import PROJECT_ROOT as _PROJECT_ROOT

from .vpa_serotyper_engine import SerotyperEngine

_DB_DIR = _PROJECT_ROOT / "data" / "reference" / "vpa_serotype"


@dataclass
class SerotypeResult:
    sample: str = ""
    o_locus: str = "None"
    k_locus: str = "None"
    o_confidence: str = "Unknown"
    k_confidence: str = "Unknown"
    o_coverage: float = 0.0
    k_coverage: float = 0.0
    o_identity: float = 0.0
    k_identity: float = 0.0
    predicted_serotype: str = "OUT:KUT"
    o_missing_genes: str = "None"
    k_missing_genes: str = "None"
    o_alerts: str = "None"
    k_alerts: str = "None"

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample": self.sample,
            "predicted_serotype": self.predicted_serotype,
            "o_locus": self.o_locus,
            "o_confidence": self.o_confidence,
            "o_coverage": self.o_coverage,
            "o_identity": self.o_identity,
            "o_missing_genes": self.o_missing_genes,
            "o_alerts": self.o_alerts,
            "k_locus": self.k_locus,
            "k_confidence": self.k_confidence,
            "k_coverage": self.k_coverage,
            "k_identity": self.k_identity,
            "k_missing_genes": self.k_missing_genes,
            "k_alerts": self.k_alerts,
        }


class VpaSerotyper:
    """V. parahaemolyticus O/K serotype predictor."""

    def __init__(self, db_dir: str | Path | None = None) -> None:
        self.db_dir = Path(db_dir) if db_dir else _DB_DIR
        self._engine: SerotyperEngine | None = None

    def _ensure_engine(self) -> SerotyperEngine:
        if self._engine is None:
            if not self.db_dir.exists():
                raise FileNotFoundError(
                    f"VPA serotype DB not found: {self.db_dir}. "
                    f"Build with build_serotype.py from GenBank files."
                )
            self._engine = SerotyperEngine(self.db_dir)
        return self._engine

    def analyze(self, contigs_path: str | Path, sample_id: str = "") -> SerotypeResult:
        if not sample_id:
            sample_id = Path(contigs_path).parent.parent.name

        try:
            engine = self._ensure_engine()
            raw = engine.run_one_sample(Path(contigs_path))

            return SerotypeResult(
                sample=raw.get("Sample", sample_id),
                o_locus=raw.get("O_Locus", "None"),
                k_locus=raw.get("K_Locus", "None"),
                o_confidence=raw.get("O_Confidence", "Unknown"),
                k_confidence=raw.get("K_Confidence", "Unknown"),
                o_coverage=raw.get("O_Coverage", 0),
                k_coverage=raw.get("K_Coverage", 0),
                o_identity=raw.get("O_Identity", 0),
                k_identity=raw.get("K_Identity", 0),
                predicted_serotype=raw.get("Predicted_Serotype", "OUT:KUT"),
                o_missing_genes=raw.get("O_Missing_Genes", "None"),
                k_missing_genes=raw.get("K_Missing_Genes", "None"),
                o_alerts=raw.get("O_Alerts", "None"),
                k_alerts=raw.get("K_Alerts", "None"),
            )
        except Exception as e:
            return SerotypeResult(
                sample=sample_id,
                o_alerts=f"Error: {e}",
                k_alerts=f"Error: {e}",
            )

    def analyze_to_json(self, contigs_path: str | Path, sample_id: str = "") -> dict[str, Any]:
        import json

        result: dict[str, Any] = json.loads(
            json.dumps(self.analyze(contigs_path, sample_id).to_dict())
        )
        return result
