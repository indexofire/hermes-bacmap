"""Tier orchestrator scripts/setup_databases.py (species-id P0)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

_SPEC = importlib.util.spec_from_file_location(
    "setup_databases", _PROJECT_ROOT / "scripts" / "setup_databases.py"
)
setup_databases = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(setup_databases)


class TestTiers:
    def test_known_tiers_listed(self):
        assert set(setup_databases.TIERS) >= {
            "none",
            "mini",
            "instant",
            "full",
            "sourmash",
            "standard",
        }

    def test_tier_meta_has_size_and_scripts(self):
        for name, meta in setup_databases.TIERS.items():
            if name == "none":
                continue
            assert "size" in meta and "scripts" in meta, name


class TestMain:
    def test_tier_none_is_noop(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["setup_databases", "--tier", "none", "--yes"])
        assert setup_databases.main() == 0

    def test_unknown_tier_rejected(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["setup_databases", "--tier", "mega", "--yes"])
        with pytest.raises(SystemExit):
            setup_databases.main()

    def test_missing_download_script_reports_clearly(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            sys,
            "argv",
            ["setup_databases", "--tier", "mini", "--yes", "--scripts-dir", str(tmp_path)],
        )
        code = setup_databases.main()
        assert code == 2
        assert "download_db_" in capsys.readouterr().out
