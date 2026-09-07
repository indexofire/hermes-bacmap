"""TDD 测试：generate_report.py --pdf（V0.7 Wave 4，project.md §2.2 PDF 报告）。

HTML → PDF 转换：headless chromium 打印优先（系统 chromium 已确认存在，
且对 D3/phylotree.js 渲染保真），weasyprint 兜底；均不可用返回 False。
单元测试 mock subprocess/shutil.which，CI 无浏览器依赖。
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import generate_report as gr  # noqa: E402


class TestHtmlToPdf:
    def test_chromium_success(self, tmp_path: Path, monkeypatch):
        html = tmp_path / "r.html"
        html.write_text("<html><body>x</body></html>")
        pdf = tmp_path / "r.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        calls: list[list[str]] = []
        monkeypatch.setattr(
            "shutil.which", lambda name: "/usr/bin/chromium" if name == "chromium" else None
        )
        monkeypatch.setattr(
            gr.subprocess,
            "run",
            lambda cmd, **kw: calls.append(cmd) or SimpleNamespace(returncode=0),
        )
        assert gr.html_to_pdf(html, pdf) is True
        assert calls and calls[0][0] == "/usr/bin/chromium"
        assert "--headless" in calls[0]
        assert any(a.startswith("--print-to-pdf=") for a in calls[0])

    def test_no_binary_no_weasyprint(self, tmp_path: Path, monkeypatch):
        html = tmp_path / "r.html"
        html.write_text("<html></html>")
        monkeypatch.setattr("shutil.which", lambda name: None)
        monkeypatch.setitem(sys.modules, "weasyprint", None)  # import 即 ImportError
        assert gr.html_to_pdf(html, tmp_path / "r.pdf") is False

    def test_chromium_failure_falls_through(self, tmp_path: Path, monkeypatch):
        """chromium 返回非零且无 weasyprint → False（不抛异常）。"""
        html = tmp_path / "r.html"
        html.write_text("<html></html>")
        monkeypatch.setattr(
            "shutil.which", lambda name: "/usr/bin/chromium" if name == "chromium" else None
        )
        monkeypatch.setattr(
            gr.subprocess,
            "run",
            lambda cmd, **kw: SimpleNamespace(returncode=1),
        )
        monkeypatch.setitem(sys.modules, "weasyprint", None)
        assert gr.html_to_pdf(html, tmp_path / "out.pdf") is False


class TestPdfFlag:
    def _sandbox(self, monkeypatch, tmp_path: Path) -> Path:
        results = tmp_path / "results"
        results.mkdir()
        monkeypatch.setattr(gr, "RESULTS_DIR", results)
        monkeypatch.setattr(gr, "ROOT", tmp_path)
        (tmp_path / "workflows/bacmap/config").mkdir(parents=True)
        (tmp_path / "workflows/bacmap/config/samples.tsv").write_text(
            "sample\tspecies\nSAM-1\tSalmonella\n"
        )
        report_dir = results / "SAM-1" / "report"
        report_dir.mkdir(parents=True)
        report_dir.joinpath("SAM-1_summary.json").write_text('{"sample": "SAM-1", "steps": {}}')
        return results

    def test_pdf_flag_converts_each_report(self, monkeypatch, tmp_path):
        self._sandbox(monkeypatch, tmp_path)
        converted: list[Path] = []
        monkeypatch.setattr(gr, "html_to_pdf", lambda html, pdf: converted.append(pdf) or True)
        rc = gr.main_args(["--sample", "SAM-1", "--pdf"])
        assert rc == 0
        assert converted and converted[0].name == "SAM-1_report.pdf"

    def test_no_pdf_flag_no_conversion(self, monkeypatch, tmp_path):
        self._sandbox(monkeypatch, tmp_path)
        converted: list[Path] = []
        monkeypatch.setattr(gr, "html_to_pdf", lambda html, pdf: converted.append(pdf) or True)
        assert gr.main_args(["--sample", "SAM-1"]) == 0
        assert converted == []
