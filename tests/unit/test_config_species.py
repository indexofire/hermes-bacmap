"""Species-ID config surface: SPECIES_DB_DIR and GTDBTK_DATA_PATH."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_PROBE = "from hermes_bacmap import config; print(config.SPECIES_DB_DIR, config.GTDB_DB)"


def _probe(env_extra: dict[str, str]) -> tuple[str, str]:
    env = {**os.environ, **env_extra, "PYTHONPATH": str(_PROJECT_ROOT / "src")}
    res = subprocess.run([sys.executable, "-c", _PROBE], env=env, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    species_db, gtdb = res.stdout.split()
    return species_db, gtdb


class TestSpeciesDbDir:
    def test_defaults_under_data(self):
        species_db, _ = _probe({})
        assert species_db.endswith("/data/db")

    def test_follows_bacmap_data_dir(self):
        species_db, _ = _probe({"BACMAP_DATA_DIR": "/tmp/alt-data"})
        assert species_db == "/tmp/alt-data/db"


class TestGtdbtkPathVariable:
    def test_gtdbtk_data_path_preferred(self):
        _, gtdb = _probe({"GTDBTK_DATA_PATH": "/a/b", "GTDBDB": "/old"})
        assert gtdb == "/a/b"

    def test_legacy_gtddb_still_honoured(self):
        _, gtdb = _probe({"GTDBDB": "/old"})
        assert gtdb == "/old"

    def test_none_when_unset(self):
        env = {k: v for k, v in os.environ.items() if k not in ("GTDBDB", "GTDBTK_DATA_PATH")}
        res = subprocess.run(
            [sys.executable, "-c", _PROBE],
            env={**env, "PYTHONPATH": str(_PROJECT_ROOT / "src")},
            capture_output=True,
            text=True,
        )
        assert res.stdout.split()[1] == "None"
