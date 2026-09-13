"""Download-script wiring for species-id plan A/D (mocked framework calls)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import _common  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _PROJECT_ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def dl(monkeypatch):
    calls: list[dict] = []

    def fake_dl(**kwargs):
        calls.append(dict(kwargs))
        return kwargs["dest_dir"]

    monkeypatch.setattr(_common, "download_database", fake_dl)
    return calls


class TestSkaniGtdb:
    def test_urls_size_and_gate(self, dl, tmp_path):
        mod = _load("download_db_skani_gtdb")
        mod.main(["--data-root", str(tmp_path)])
        assert dl[0]["urls"][0] == (
            "http://faust.compbio.cs.cmu.edu/skani-files/skani_gtdb_r226-v0.3.tar.gz"
        )
        assert dl[0]["name"] == "skani_gtdb"
        assert dl[0]["expected_size_gb"] == pytest.approx(30.0)
        assert dl[0]["min_free_gb"] == pytest.approx(110.0)


class TestMashRefseq:
    def test_zenodo_md5(self, dl, tmp_path):
        mod = _load("download_db_mash_refseq")
        mod.main(["--data-root", str(tmp_path)])
        assert dl[0]["urls"][0].startswith("https://zenodo.org/")
        assert dl[0]["expected_md5"] == "dee53b23af3ab120333f9eb1b95ae60f"
        assert dl[0]["name"] == "mash_refseq"
