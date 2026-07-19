"""End-to-end tests for the VPA serotyper against real reference genomes.

Runs the full minimap2 + sourmash + gene-level pipeline on the tracked
reference genomes (data/reference/genomes/) with the tracked serotype DB
(data/reference/vpa_serotype/). Skips when mappy/sourmash or the DB is
unavailable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("mappy", reason="mappy not installed")
pytest.importorskip("sourmash", reason="sourmash not installed")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.typing.vpa_serotyper import VpaSerotyper  # noqa: E402
from hermes_bacmap.typing.vpa_serotyper_engine import SerotyperEngine  # noqa: E402

_DB_DIR = _PROJECT_ROOT / "data" / "reference" / "vpa_serotype"
_GENOMES = _PROJECT_ROOT / "data" / "reference" / "genomes"

pytestmark = pytest.mark.skipif(
    not (_DB_DIR / "ref_seqs.fasta").exists(),
    reason="VPA serotype DB not available",
)


@pytest.fixture(scope="module")
def serotyper() -> VpaSerotyper:
    return VpaSerotyper(_DB_DIR)


@pytest.fixture(scope="module")
def engine(serotyper: VpaSerotyper) -> SerotyperEngine:
    return serotyper._ensure_engine()


class TestRimdO3K6:
    """RIMD 2210633 is the canonical O3:K6 pandemic strain."""

    def test_perfect_o3k6(self, serotyper):
        r = serotyper.analyze(_GENOMES / "vpara_rimd.fasta", "vpara_rimd")
        assert r.predicted_serotype == "O3:K6"
        assert r.o_locus == "OL3"
        assert r.k_locus == "KL6"
        assert r.o_confidence == "Perfect"
        assert r.k_confidence == "Perfect"
        assert r.o_coverage == 100.0
        assert r.k_coverage == 100.0
        assert r.o_missing_genes == "None"
        assert r.o_alerts == "None"

    def test_detail_report_fields(self, engine):
        raw = engine.run_one_sample(_GENOMES / "vpara_rimd.fasta", enable_detail=True)
        assert raw["Predicted_Serotype"] == "O3:K6"
        # Perfect 且无相近候选时 detail notes 按设计为空,但报告字段必须存在
        assert "O_Detail" in raw and "K_Detail" in raw
        assert raw["O_Genes_Detail"]
        assert raw["K_Genes_Detail"]
        assert raw["O_Expected_In_Locus_Detail"]

    def test_reference_genes(self, engine):
        genes = engine.get_reference_genes("OL3")
        assert len(genes) > 5
        assert all("name" in g and "start" in g and "end" in g for g in genes)
        assert engine.get_reference_genes("NO_SUCH_LOCUS") == []


class TestNegativeControl:
    def test_salmonella_untypeable(self, serotyper):
        r = serotyper.analyze(_GENOMES / "salmonella_LT2.fasta", "salmonella_LT2")
        assert r.predicted_serotype == "OUT:KUT"
        assert r.o_locus == "None"
        assert r.k_locus == "None"
        assert r.o_confidence == "Unknown"

    def test_ecoli_untypeable(self, serotyper):
        r = serotyper.analyze(_GENOMES / "ecoli_k12.fasta", "ecoli_k12")
        assert r.predicted_serotype == "OUT:KUT"
        assert r.o_locus == "None"
