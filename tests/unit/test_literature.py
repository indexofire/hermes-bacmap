"""Unit tests for literature connector (services/literature.py).

urlopen is mocked at the services.literature module boundary; canned Europe
PMC JSON fixtures verified against the live API response shape.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.services.literature import lit_search  # noqa: E402

_MOD = "hermes_bacmap.services.literature"

EPMC_RESPONSE = {
    "hitCount": 1065,
    "resultList": {
        "result": [
            {
                "id": "42551606",
                "source": "MED",
                "pmid": "42551606",
                "pmcid": None,
                "doi": "10.1016/j.micpath.2026.108752",
                "title": "Differential pathogenic contributions of tdh/trh genes",
                "journalTitle": "Microbial Pathogenesis",
                "pubYear": "2026",
                "authorString": "Fu G, Xu H, Zhu L, et al",
                "abstractText": "tdh-positive strains showed higher cytotoxicity. " * 8,
            },
            {
                "id": "40123001",
                "source": "MED",
                "pmid": "40123001",
                "pmcid": "PMC1234567",
                "doi": "10.1128/aem.00123-26",
                "title": "Outbreak of V. parahaemolyticus traced to oysters",
                "journalTitle": "Applied and Environmental Microbiology",
                "pubYear": "2026",
                "authorString": "Chen L, et al",
                "abstractText": "Foodborne outbreak investigation. " * 4,
            },
        ]
    },
}


class _FakeBody(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


def _fake_urlopen(response: dict):
    def urlopen(req, timeout=None):
        return _FakeBody(json.dumps(response).encode())

    return urlopen


class TestLitSearch:
    def test_returns_hits_with_citations(self):
        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(EPMC_RESPONSE)) as u:
            result = lit_search("tdh virulence", max_results=2)

        assert result["total_hits"] == 1065
        assert len(result["papers"]) == 2
        first = result["papers"][0]
        assert first["title"].startswith("Differential pathogenic")
        assert first["pmid"] == "42551606"
        assert first["doi"].startswith("10.1016")
        assert first["year"] == "2026"
        assert first["citation"] == (
            "Fu G, Xu H, Zhu L, et al. Differential pathogenic contributions of "
            "tdh/trh genes. Microbial Pathogenesis (2026). PMID:42551606"
        )
        assert len(first["abstract"]) <= 500

        called_url = u.call_args.args[0]
        assert "europepmc/webservices/rest/search" in called_url
        assert "format=json" in called_url

    def test_builds_query_url_with_params(self):
        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(EPMC_RESPONSE)) as u:
            lit_search("salmonella invA", max_results=5)

        url = u.call_args.args[0]
        assert "query=salmonella+invA" in url
        assert "pageSize=5" in url
        assert "resultType=core" in url

    def test_empty_result_list(self):
        empty = {"hitCount": 0, "resultList": {"result": []}}
        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(empty)):
            result = lit_search("xyzzy nonexistent")

        assert result["total_hits"] == 0
        assert result["papers"] == []

    def test_http_error_raises_runtimeerror(self):
        import urllib.error

        with patch(
            f"{_MOD}.urlopen",
            side_effect=urllib.error.URLError("network down"),
        ):
            with pytest.raises(RuntimeError, match="Europe PMC"):
                lit_search("anything")

    def test_malformed_json_raises_runtimeerror(self):
        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen({"unexpected": 1})):
            with pytest.raises(RuntimeError, match="unexpected response"):
                lit_search("anything")


class TestLitSearchDomainQuery:
    def test_disease_query_appends_context(self):
        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(EPMC_RESPONSE)) as u:
            lit_search("novel virulence marker")

        url = u.call_args.args[0]
        assert "novel+virulence+marker" in url


class TestLitSearchHandler:
    def test_handler_returns_json_result(self):
        from hermes_bacmap.tools import lit_search as handler

        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(EPMC_RESPONSE)):
            out = handler({"query": "tdh", "max_results": 2})

        import json as _json

        d = _json.loads(out)
        assert d["source"] == "europepmc"
        assert len(d["papers"]) == 2

    def test_handler_empty_query_returns_error(self):
        from hermes_bacmap.tools import lit_search as handler

        out = handler({"query": "  "})
        assert "error" in json.loads(out)

    def test_handler_network_error_returns_error_json(self):
        import urllib.error

        from hermes_bacmap.tools import lit_search as handler

        with patch(f"{_MOD}.urlopen", side_effect=urllib.error.URLError("down")):
            out = handler({"query": "x"})

        assert "error" in json.loads(out)
