"""Tests for config.py — central path resolution."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))


class TestConfigDefaults:
    def test_project_root_exists(self):
        from hermes_bacmap.config import PROJECT_ROOT

        assert PROJECT_ROOT.exists()

    def test_data_dir_exists(self):
        from hermes_bacmap.config import DATA_DIR

        assert DATA_DIR.exists()

    def test_ref_dir_has_fastas(self):
        from hermes_bacmap.config import REF_DIR

        assert REF_DIR.exists()
        assert any(REF_DIR.rglob("*.fasta"))

    def test_db_path_points_to_data(self):
        from hermes_bacmap.config import DB_PATH

        assert DB_PATH.name == "hermes_bacmap.sqlite"
        assert DB_PATH.parent.name == "data"

    def test_results_dir(self):
        from hermes_bacmap.config import RESULTS_DIR

        assert RESULTS_DIR.name == "results"

    def test_pixi_bin(self):
        from hermes_bacmap.config import PIXI_BIN

        assert "bin" in PIXI_BIN


class TestConfigEnvVars:
    def test_bacmap_data_dir_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BACMAP_DATA_DIR", str(tmp_path))
        import importlib

        import hermes_bacmap.config

        importlib.reload(hermes_bacmap.config)
        assert hermes_bacmap.config.DATA_DIR == tmp_path
        assert hermes_bacmap.config.REF_DIR == tmp_path / "reference"
        assert hermes_bacmap.config.DB_PATH == tmp_path / "hermes_bacmap.sqlite"
        importlib.reload(hermes_bacmap.config)

    def test_bacmap_db_path_override(self, tmp_path, monkeypatch):
        custom_db = tmp_path / "custom.sqlite"
        monkeypatch.setenv("BACMAP_DB_PATH", str(custom_db))
        import importlib

        import hermes_bacmap.config

        importlib.reload(hermes_bacmap.config)
        assert hermes_bacmap.config.DB_PATH == custom_db
        importlib.reload(hermes_bacmap.config)

    def test_bacmap_results_dir_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BACMAP_RESULTS_DIR", str(tmp_path))
        import importlib

        import hermes_bacmap.config

        importlib.reload(hermes_bacmap.config)
        assert hermes_bacmap.config.RESULTS_DIR == tmp_path
        importlib.reload(hermes_bacmap.config)
