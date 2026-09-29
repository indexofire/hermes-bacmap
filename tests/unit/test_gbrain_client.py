"""Unit tests for the GBrain client bridge (services/gbrain_client.py).

gbrain CLI is mocked at the subprocess boundary; binary resolution via
config.which. The bridge talks to `gbrain call <op> '<json>'` (JSON in/out)
plus dedicated verbs (capture/search/think) with --json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.services.gbrain_client import (  # noqa: E402
    GbrainBusyError,
    GbrainUnavailable,
    capture,
    capture_evidence,
    gbrain_call,
    search,
    think,
)

_MOD = "hermes_bacmap.services.gbrain_client"

CAPTURE_RECEIPT = {
    "request_id": "5a1f-001",
    "state": "committed",
    "slug": "inbox/2026-09-29-abc12345",
    "content_hash": "abc12345",
    "status": "captured",
}

SEARCH_RESULTS = [
    {
        "slug": "amr-gene-reference",
        "title": "AMR gene reference",
        "chunk_text": "blaCTX-M ... clinical priority",
        "score": 0.92,
    },
    {"slug": "snp-thresholds", "title": "SNP thresholds", "chunk_text": "...", "score": 0.81},
]

THINK_ANSWER = {
    "answer": "blaCMY-2 is an AmpC cephalosporinase...",
    "citations": [{"slug": "amr-gene-reference", "title": "AMR gene reference"}],
    "gaps": [],
}


def _proc(stdout: str = "", stderr: str = "", returncode: int = 0) -> CompletedProcess:
    return CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestGbrainCall:
    def test_builds_call_argv_and_parses_json(self):
        with (
            patch(f"{_MOD}.which", return_value="/fake/gbrain"),
            patch(f"{_MOD}.subprocess.run", return_value=_proc(json.dumps({"ok": 1}))) as run,
        ):
            out = gbrain_call("get_stats", {})

        assert out == {"ok": 1}
        cmd = run.call_args.args[0]
        assert cmd[:3] == ["/fake/gbrain", "call", "get_stats"]
        assert json.loads(cmd[3]) == {}

    def test_missing_binary_raises_with_hint(self):
        with patch(f"{_MOD}.which", return_value=None):
            with pytest.raises(GbrainUnavailable, match="gbrain not found"):
                gbrain_call("search", {"query": "x"})

    def test_nonzero_exit_raises_runtimeerror(self):
        with (
            patch(f"{_MOD}.which", return_value="/fake/gbrain"),
            patch(f"{_MOD}.subprocess.run", return_value=_proc(stderr="bad op", returncode=1)),
        ):
            with pytest.raises(RuntimeError, match="bad op"):
                gbrain_call("nope", {})

    def test_pglite_busy_raises_retryable(self):
        busy = json.dumps({"error": "pglite_busy", "retryable": True})
        with (
            patch(f"{_MOD}.which", return_value="/fake/gbrain"),
            patch(f"{_MOD}.subprocess.run", return_value=_proc(stdout=busy, returncode=3)),
        ):
            with pytest.raises(GbrainBusyError):
                gbrain_call("search", {"query": "x"})

    def test_timeout_kills_long_call(self):
        import subprocess

        with (
            patch(f"{_MOD}.which", return_value="/fake/gbrain"),
            patch(
                f"{_MOD}.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="gbrain", timeout=5),
            ),
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                gbrain_call("think", {"question": "x"}, timeout=5)


class TestCapture:
    def test_capture_returns_receipt_and_forwards_params(self):
        with (
            patch(f"{_MOD}.which", return_value="/fake/gbrain"),
            patch(f"{_MOD}.subprocess.run", return_value=_proc(json.dumps(CAPTURE_RECEIPT))) as run,
        ):
            receipt = capture(
                "Lab X found ST34 carrying mcr-1",
                tags=["amr", "field"],
                kind="finding",
            )

        assert receipt["state"] == "committed"
        payload = json.loads(run.call_args.args[0][3])
        assert "mcr-1" in payload["content"]
        assert payload["kind"] == "finding"
        front = payload["content"].split("---")[1]
        assert "tags" in front

    def test_capture_evidence_builds_structured_frontmatter(self):
        page = capture_evidence(
            summary="novel cluster_0042 enriched 11/12 vs 0/8",
            species="Salmonella enterica",
            gene="cluster_0042",
            strain_group="outbreak-2026-09",
            evidence="pangenome/presence_matrix.parquet",
            kind="novel-marker",
        )

        assert page.startswith("---")
        front = page.split("---")[1]
        for key in ("species", "gene", "strain_group", "evidence", "kind", "captured_via"):
            assert key in front, key
        assert "cluster_0042 enriched" in page.split("---", 2)[2]

    def test_capture_evidence_rejects_newline_injection(self):
        with pytest.raises(ValueError, match="gene"):
            capture_evidence(
                summary="x",
                species="Salmonella",
                gene="evil\ngene: hacked",
                strain_group="g",
                evidence="e",
                kind="k",
            )


class TestSearchAndThink:
    def test_search_returns_results(self):
        with (
            patch(f"{_MOD}.which", return_value="/fake/gbrain"),
            patch(
                f"{_MOD}.subprocess.run",
                return_value=_proc(json.dumps({"results": SEARCH_RESULTS})),
            ) as run,
        ):
            results = search("blaCTX", limit=5)

        assert len(results) == 2
        assert results[0]["slug"] == "amr-gene-reference"
        args = json.loads(run.call_args.args[0][3])
        assert args["query"] == "blaCTX"
        assert args["limit"] == 5

    def test_search_accepts_bare_list_response(self):
        with (
            patch(f"{_MOD}.which", return_value="/fake/gbrain"),
            patch(f"{_MOD}.subprocess.run", return_value=_proc(json.dumps(SEARCH_RESULTS))),
        ):
            assert len(search("x")) == 2

    def test_think_returns_answer_with_citations(self):
        with (
            patch(f"{_MOD}.which", return_value="/fake/gbrain"),
            patch(f"{_MOD}.subprocess.run", return_value=_proc(json.dumps(THINK_ANSWER))) as run,
        ):
            out = think("clinical significance of blaCMY-2?")

        assert out["answer"].startswith("blaCMY-2")
        assert out["citations"][0]["slug"] == "amr-gene-reference"
        args = json.loads(run.call_args.args[0][3])
        assert args["question"].startswith("clinical")
