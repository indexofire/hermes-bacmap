"""TDD for GOM typing ANALYSIS payload schemas (Phase 3C)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.services.genome_object_service import (  # noqa: E402
    GOMValidationError,
    GenomeObject,
    GenomeObjectService,
    ObjectType,
)

_NOW = datetime(2026, 9, 28, 12, 0, 0, tzinfo=UTC)


def _analysis(payload: dict, oid: str = "00000000-0000-4000-8000-0000000000dd") -> GenomeObject:
    return GenomeObject(
        object_id=oid,
        object_type=ObjectType.ANALYSIS,
        version=1,
        schema_version="0.1.0",
        created_at=_NOW,
        created_by="test",
        payload=payload,
        pipeline_version="phase3-typing-v0.1",
        database_versions={"markers_v2": "abc12345"},
        strain_id="SAM-TYP-001",
    )


class TestTypingPayloadSchemas:
    def test_vcholerae_genotype_payload(self, tmp_path):
        payload = {
            "analysis_type": "toxin_genotype",
            "pathogen": "Vibrio cholerae",
            "result": {
                "species": "Vibrio cholerae",
                "toxigenic": True,
                "ctxa_positive": True,
                "ompw_positive": True,
            },
        }
        with GenomeObjectService(tmp_path / "gom.sqlite") as gos:
            gos.create(_analysis(payload))

    def test_lmono_serogroup_payload(self, tmp_path):
        payload = {
            "analysis_type": "serogroup",
            "pathogen": "Listeria monocytogenes",
            "result": {
                "species": "Listeria monocytogenes",
                "serogroup": "4b",
                "confidence": "high",
            },
        }
        with GenomeObjectService(tmp_path / "gom.sqlite") as gos:
            gos.create(_analysis(payload))

    def test_cdiff_toxin_payload(self, tmp_path):
        payload = {
            "analysis_type": "toxin_genotype",
            "pathogen": "Clostridioides difficile",
            "result": {
                "species": "Clostridioides difficile",
                "toxigenic": True,
                "possible_rt027": True,
            },
        }
        with GenomeObjectService(tmp_path / "gom.sqlite") as gos:
            gos.create(_analysis(payload))

    def test_bcereus_toxin_payload(self, tmp_path):
        payload = {
            "analysis_type": "toxin_genotype",
            "pathogen": "Bacillus cereus",
            "result": {"toxin_type": "emetic"},
        }
        with GenomeObjectService(tmp_path / "gom.sqlite") as gos:
            gos.create(_analysis(payload))

    def test_species_identification_still_valid(self, tmp_path):
        payload = {
            "analysis_type": "species_identification",
            "method": "multigene",
            "database": {"name": "markers_v2", "version": "abc123"},
            "result": {"species": "Salmonella", "confidence": "high"},
        }
        with GenomeObjectService(tmp_path / "gom.sqlite") as gos:
            gos.create(_analysis(payload))

    def test_unknown_analysis_type_still_opaque(self, tmp_path):
        payload = {
            "analysis_type": "custom_future_analysis",
            "data": {"anything": "goes"},
        }
        with GenomeObjectService(tmp_path / "gom.sqlite") as gos:
            gos.create(_analysis(payload))
