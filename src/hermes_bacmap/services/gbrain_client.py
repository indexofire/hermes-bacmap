"""GBrain client bridge — knowledge-layer integration via the gbrain CLI.

Wraps `gbrain call <op> '<json>'` (JSON in/out, covers every gbrain op
including capture/search/think) so the plugin needs no MCP client library.
Binary resolved via config.which (user-level bun install); PGLite lock
contention surfaces as retryable GbrainBusyError; all failures degrade to
clear errors, never raises into tool handlers unchecked.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from ..config import which

_TIMEOUT_S = 120
_THINK_TIMEOUT_S = 300


class GbrainUnavailable(RuntimeError):
    pass


class GbrainBusyError(RuntimeError):
    pass


def _find_bin() -> str:
    found = which("gbrain")
    if not found:
        raise GbrainUnavailable(
            "gbrain not found in PATH. Install (user-level): "
            "git clone --depth 1 https://github.com/garrytan/gbrain.git ~/gbrain && "
            "cd ~/gbrain && bun install && ln -sf ~/gbrain/src/cli.ts ~/.bun/bin/gbrain"
        )
    return found


def gbrain_call(op: str, args: dict[str, Any], timeout: int = _TIMEOUT_S) -> Any:
    cmd = [_find_bin(), "call", op, json.dumps(args, ensure_ascii=False)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"gbrain {op} timed out after {timeout}s") from e

    body = _decode(result.stdout)
    if (
        isinstance(body, dict)
        and body.get("retryable")
        and "pglite_busy" in str(body.get("error", ""))
    ):
        raise GbrainBusyError("gbrain datastore locked (pglite_busy) — retry shortly")

    if result.returncode != 0:
        detail = result.stderr.strip()[:300] or str(body)[:300]
        raise RuntimeError(f"gbrain {op} failed: {detail}")

    if isinstance(body, dict) and isinstance(body.get("error"), str):
        raise RuntimeError(f"gbrain {op} failed: {body['error'][:300]}")
    return body


def _decode(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        first_json = text.find("{")
        if first_json >= 0:
            try:
                return json.loads(text[first_json:])
            except json.JSONDecodeError:
                pass
        return {"raw": text[:500]}


def capture(
    content: str,
    slug: str = "",
    tags: list[str] | None = None,
    kind: str = "",
    who: str = "hermes-bacmap",
    what: str = "",
) -> dict[str, Any]:
    front: dict[str, Any] = {"captured_via": "hermes-bacmap"}
    if tags:
        front["tags"] = tags
    if kind:
        front["kind"] = kind
    frontmatter = (
        "---\n"
        + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in front.items())
        + "\n---\n"
    )

    args: dict[str, Any] = {"content": frontmatter + content + "\n"}
    if slug:
        args["slug"] = slug
    if kind:
        args["kind"] = kind
    if who:
        args["who"] = who
    if what:
        args["what"] = what

    receipt = gbrain_call("capture", args)
    return receipt if isinstance(receipt, dict) else {"raw": receipt}


def capture_evidence(
    summary: str,
    species: str,
    gene: str,
    strain_group: str,
    evidence: str,
    kind: str,
    tags: list[str] | None = None,
) -> str:
    for key, value in (("species", species), ("gene", gene), ("strain_group", strain_group)):
        if not value or "\n" in value or ":" in value:
            raise ValueError(f"invalid {key}: {value!r}")

    front: dict[str, Any] = {
        "species": species,
        "gene": gene,
        "strain_group": strain_group,
        "evidence": evidence,
        "kind": kind,
        "captured_via": "hermes-bacmap",
        "tags": tags or [kind],
    }
    frontmatter = (
        "---\n"
        + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in front.items())
        + "\n---\n"
    )
    return frontmatter + summary + "\n"


def search(query: str, limit: int = 20) -> list[dict[str, Any]]:
    body = gbrain_call("search", {"query": query, "limit": max(1, min(int(limit), 100))})
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        results = body.get("results")
        if isinstance(results, list):
            return results
    return []


def think(question: str, anchor: str = "") -> dict[str, Any]:
    args: dict[str, Any] = {"question": question, "save": False}
    if anchor:
        args["anchor"] = anchor
    body = gbrain_call("think", args, timeout=_THINK_TIMEOUT_S)
    return body if isinstance(body, dict) else {"raw": body}
