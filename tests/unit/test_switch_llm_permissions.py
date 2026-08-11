"""Security tests for switch_llm.py — written config must be mode 0600.

api_key values land in ~/.hermes/config.yaml in plaintext; without restrictive
permissions, other users on the host can read LLM provider credentials.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

from switch_llm import write_config  # noqa: E402


def test_write_config_sets_mode_0600(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("model:\n  default: old\n")
    backup = tmp_path / "config.yaml.bak"
    monkeypatch.setattr("switch_llm.HERMES_CONFIG", config)

    write_config("model:\n  default: new\n  api_key: s3cret\n")

    assert oct(config.stat().st_mode & 0o777) == "0o600"
    assert oct(backup.stat().st_mode & 0o777) == "0o600"


def test_write_config_preserves_content(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("old\n")
    monkeypatch.setattr("switch_llm.HERMES_CONFIG", config)

    write_config("new content with api_key: xyz\n")

    assert config.read_text() == "new content with api_key: xyz\n"
    # backup retains pre-write content
    assert (tmp_path / "config.yaml.bak").read_text() == "old\n"
