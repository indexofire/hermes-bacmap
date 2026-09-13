"""Species-ID validation judge logic (truth-table scoring)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

_SPEC = importlib.util.spec_from_file_location(
    "validate_species_id", _PROJECT_ROOT / "scripts" / "validate_species_id.py"
)
vsi = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vsi)


class TestJudge:
    def test_salmonella_target_exact(self):
        assert vsi.judge("Salmonella", "Salmonella", "target")

    def test_ecoli_accepts_dec_and_shigella_labels(self):
        assert vsi.judge("E.coli/Shigella", "DEC", "target")
        assert vsi.judge("E.coli/Shigella", "Shigella/EIEC", "target")

    def test_target_miss(self):
        assert not vsi.judge("Salmonella", "DEC", "target")

    def test_unknown_fails_target(self):
        assert not vsi.judge("V.parahaemolyticus", "Unknown", "target")

    def test_mash_species_name_match(self):
        assert vsi.judge("Salmonella", "Salmonella_enterica_GCF_123", "target")
        assert vsi.judge("V.parahaemolyticus", "Vibrio_parahaemolyticus_RIMD", "target")

    def test_negative_passes_when_not_target_species(self):
        assert vsi.judge("L.monocytogenes_negative", "Listeria_monocytogenes_X", "negative")

    def test_negative_fails_when_claims_target(self):
        assert not vsi.judge("V.alginolyticus_negative", "Vibrio_parahaemolyticus_RIMD", "negative")

    def test_negative_unknown_passes(self):
        assert vsi.judge("K.pneumoniae_negative", "Unknown", "negative")
