"""Download framework in scripts/_common.py (species-id P0)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import _common  # noqa: E402


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


@pytest.fixture
def disk_ok(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "disk_usage", lambda p: type("U", (), {"free": 10**12})())


class TestDownloadDatabase:
    def test_fetches_and_writes_manifest(self, tmp_path, disk_ok, monkeypatch):
        payload = b">genome\nACGT\n"
        monkeypatch.setattr(_common, "_fetch", lambda urls, dest: dest.write_bytes(payload))
        dest_dir = tmp_path / "db" / "demo"
        result = _common.download_database(
            name="demo",
            urls=["https://mirror.example/demo.tar.gz"],
            dest_dir=dest_dir,
            expected_md5=_md5(payload),
            expected_size_gb=0.01,
        )
        assert result == dest_dir
        manifest = json.loads((tmp_path / "db" / "manifests" / "demo.json").read_text())
        assert manifest["name"] == "demo"
        assert manifest["source_url"] == "https://mirror.example/demo.tar.gz"
        assert manifest["checksum"] == _md5(payload)

    def test_idempotent_when_manifest_and_checksum_match(self, tmp_path, disk_ok, monkeypatch):
        payload = b"deadbeef"
        calls = []
        monkeypatch.setattr(
            _common,
            "_fetch",
            lambda urls, dest: (calls.append(1), dest.write_bytes(payload)) and None,
        )
        dest_dir = tmp_path / "db" / "demo"
        _common.download_database(
            "demo", ["https://x/y"], dest_dir, expected_md5=_md5(payload), expected_size_gb=0.01
        )
        _common.download_database(
            "demo", ["https://x/y"], dest_dir, expected_md5=_md5(payload), expected_size_gb=0.01
        )
        assert len(calls) == 1

    def test_checksum_mismatch_raises(self, tmp_path, disk_ok, monkeypatch):
        monkeypatch.setattr(_common, "_fetch", lambda urls, dest: dest.write_bytes(b"corrupt"))
        with pytest.raises(_common.DatabaseDownloadError, match="md5"):
            _common.download_database(
                "demo",
                ["https://x/y"],
                tmp_path / "db" / "demo",
                expected_md5=_md5(b"good"),
                expected_size_gb=0.01,
            )

    def test_disk_precheck_rejects(self, tmp_path, monkeypatch):
        import shutil

        monkeypatch.setattr(shutil, "disk_usage", lambda p: type("U", (), {"free": 1000})())
        with pytest.raises(_common.DatabaseDownloadError, match="disk"):
            _common.download_database(
                "demo",
                ["https://x/y"],
                tmp_path / "db" / "demo",
                expected_size_gb=5.0,
                min_free_gb=1.0,
            )

    def test_ram_gate_rejects(self, tmp_path, disk_ok, monkeypatch):
        monkeypatch.setattr(_common, "_available_ram_gb", lambda: 64.0)
        with pytest.raises(_common.DatabaseDownloadError, match="[Rr][Aa][Mm]"):
            _common.download_database(
                "gtdbtk",
                ["https://x/y"],
                tmp_path / "db" / "g",
                expected_size_gb=1.0,
                min_ram_gb=140.0,
            )
