"""L2 sandbox executor — controlled code exploration with human review.

Runs AI-written Python in a subprocess (cwd = per-session sandbox dir) with
timeout, captured stdout/stderr, and pickle-based session variable
persistence. Per project.md §L2: sandboxed exploration results enter
reports only after user sign-off; executed code files are persisted in the
session dir for audit.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

RESULTS_DIR_FIELD = "BACMAP_RESULTS"
_VARS_FILE = "_vars.pkl"
_VARS_MARKER = "SESSION_VARS:"
_RUNNER = f"""\
import pickle, sys, os
ns = {{}}
if os.path.exists({_VARS_FILE!r}):
    with open({_VARS_FILE!r}, 'rb') as f:
        ns = pickle.load(f)
with open(sys.argv[1]) as f:
    exec(compile(f.read(), sys.argv[1], 'exec'), ns)
keep = {{}}
for k, v in ns.items():
    if k.startswith('__'):
        continue
    try:
        pickle.dumps(v)
    except Exception:
        continue
    keep[k] = v
with open({_VARS_FILE!r}, 'wb') as f:
    pickle.dump(keep, f)
print({_VARS_MARKER!r}, ', '.join(sorted(keep)))
"""


def exec_code(
    code: str,
    session: str = "default",
    timeout: int = 60,
    sandbox_root: Path | None = None,
    results_dir: Path | None = None,
) -> dict[str, Any]:
    if sandbox_root is None:
        from ..config import RESULTS_DIR

        sandbox_root = RESULTS_DIR / "sandbox"
    session = session if session else "default"

    session_dir = Path(sandbox_root) / session
    session_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(session_dir.glob("run_*.py"))
    run_file = session_dir / f"run_{len(existing) + 1:04d}.py"
    run_file.write_text(code, encoding="utf-8")

    runner_file = session_dir / "_runner.py"
    runner_file.write_text(_RUNNER, encoding="utf-8")

    env: dict[str, str] | None = None
    if results_dir is not None:
        import os

        env = dict(os.environ)
        env[RESULTS_DIR_FIELD] = str(results_dir)

    timed_out = False
    try:
        proc = subprocess.run(
            [sys.executable, "-u", runner_file.name, run_file.name],
            cwd=session_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        stdout, stderr, exit_code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        timed_out = True
        stdout = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = f"timeout after {timeout}s"
        exit_code = -1

    variables = _parse_vars(stdout)
    return {
        "session": session,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
        "variables": variables,
        "code_file": str(run_file),
    }


def _parse_vars(stdout: str) -> list[str]:
    for line in stdout.splitlines():
        if line.startswith(_VARS_MARKER):
            rest = line[len(_VARS_MARKER) :].strip()
            return [v.strip() for v in rest.split(",") if v.strip()] if rest else []
    return []
