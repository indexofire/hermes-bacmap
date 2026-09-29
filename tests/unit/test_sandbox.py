"""Unit tests for the L2 sandbox executor (analysis/sandbox.py).

Real subprocess execution (python -c runner) against tmp_path sandbox dirs;
session variables persist via pickle across exec calls in one session.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.analysis.sandbox import exec_code  # noqa: E402


class TestExecCode:
    def test_returns_stdout_and_exit_code(self, tmp_path):
        result = exec_code("print('hello', 1 + 1)", sandbox_root=tmp_path)

        assert result["exit_code"] == 0
        assert "hello 2" in result["stdout"]
        assert result["stderr"] == ""
        assert result["timed_out"] is False

    def test_captures_stderr_and_traceback(self, tmp_path):
        result = exec_code("raise ValueError('boom')", sandbox_root=tmp_path)

        assert result["exit_code"] != 0
        assert "ValueError" in result["stderr"] or "boom" in result["stderr"]

    def test_timeout_kills_runaway_code(self, tmp_path):
        result = exec_code("import time; time.sleep(30)", timeout=2, sandbox_root=tmp_path)

        assert result["timed_out"] is True
        assert result["exit_code"] != 0

    def test_session_variables_persist_across_calls(self, tmp_path):
        first = exec_code("x = 42; y = 'strain'", session="s1", sandbox_root=tmp_path)
        assert "x" in first["variables"]

        second = exec_code("print('x is', x)", session="s1", sandbox_root=tmp_path)
        assert "x is 42" in second["stdout"]

    def test_sessions_are_isolated(self, tmp_path):
        exec_code("secret = 99", session="s1", sandbox_root=tmp_path)
        other = exec_code("print('secret' in dir())", session="s2", sandbox_root=tmp_path)

        assert "False" in other["stdout"]

    def test_unpicklable_variables_dropped_not_fatal(self, tmp_path):
        result = exec_code(
            "import threading; lock = threading.Lock(); keep = 7",
            sandbox_root=tmp_path,
        )

        assert result["exit_code"] == 0
        assert "keep" in result["variables"]
        assert "lock" not in result["variables"]

    def test_timeout_output_still_captured(self, tmp_path):
        result = exec_code(
            "print('before'); import time; time.sleep(30)",
            timeout=2,
            sandbox_root=tmp_path,
        )

        assert result["timed_out"] is True
        assert "before" in result["stdout"]

    def test_results_dir_available_as_r(self, tmp_path):
        from hermes_bacmap.analysis.sandbox import RESULTS_DIR_FIELD

        (tmp_path / "results").mkdir()
        code = (
            "import os; d = os.environ.get('BACMAP_RESULTS', '')\n"
            "print('R_OK' if os.path.isdir(d) else 'R_MISSING')"
        )
        result = exec_code(
            code, results_dir=tmp_path / "results", sandbox_root=tmp_path
        )
        assert RESULTS_DIR_FIELD == "BACMAP_RESULTS"
        assert "R_OK" in result["stdout"]

    def test_code_file_persisted_for_audit(self, tmp_path):
        exec_code("audit_marker = 1", session="audit1", sandbox_root=tmp_path)

        session_dir = tmp_path / "audit1"
        code_files = sorted(session_dir.glob("run_*.py"))
        assert code_files, "executed code must be persisted for audit (L2 human review)"
