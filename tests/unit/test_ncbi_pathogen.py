"""Unit tests for NCBI Pathogen Detection connector (services/ncbi_pathogen.py).

urlopen mocked at module boundary; canned responses replicate the verified
pathogens-srv contract: {"success": true, "ngout": {"data": {"content":
[...], "totalCount": N}}}.

The endpoint is the Isolates Browser's own backend (undocumented but
publicly reachable, no key): action=retrieve&collection=isolates, with SOLR
`fq` filters, `fl` field list, `start`/`limit` paging.
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

from hermes_bacmap.services.ncbi_pathogen import (  # noqa: E402
    pathogen_amr_elements,
    pathogen_isolates,
)

_MOD = "hermes_bacmap.services.ncbi_pathogen"

ISOLATES_RESPONSE = {
    "success": True,
    "ngout": {
        "data": {
            "totalCount": 768,
            "content": [
                {
                    "target_acc": "PDT003403356.1",
                    "biosample_acc": "SAMN63557232",
                    "taxgroup_name": "Salmonella enterica",
                    "scientific_name": "Salmonella enterica",
                    "serovar": "Enteritidis",
                    "geo_loc_name": "USA:LA",
                    "isolation_source": "Yolk sac",
                    "collection_date": "2026-03-16",
                    "epi_type": "clinical",
                    "strain": "PNUSAS607689",
                    "AST_phenotypes": ["ampicillin=S", "streptomycin=R"],
                    "AMR_genotypes": ["mdsA=COMPLETE"],
                }
            ],
        }
    },
}

AMR_RESPONSE = {
    "success": True,
    "ngout": {
        "data": {
            "totalCount": 16434388,
            "content": [
                {
                    "target_acc": "PDT000039560.2",
                    "element_symbol": "pagK",
                    "element_name": "vesicle-borne virulence factor PagK",
                    "element_length": 66,
                    "closest_reference_name": "pagK Salmonella enterica",
                    "scientific_name": "Salmonella enterica",
                    "geo_loc_name": "USA",
                }
            ],
        }
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
        if not any("hermes-bacmap" in str(h) for h in req.headers.values()):
            raise AssertionError("request must carry a descriptive User-Agent")
        return _FakeBody(json.dumps(response).encode())

    return urlopen


class TestPathogenIsolates:
    def test_returns_isolates_with_total(self):
        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(ISOLATES_RESPONSE)) as u:
            result = pathogen_isolates(organism="Salmonella enterica", max_results=10)

        assert result["total"] == 768
        iso = result["isolates"][0]
        assert iso["target_acc"] == "PDT003403356.1"
        assert iso["geo"] == "USA:LA"
        assert iso["ast"][0] == "ampicillin=S"

        url = u.call_args.args[0].full_url
        assert "action=retrieve" in url
        assert "collection=isolates" in url
        assert "start=0" in url
        assert "limit=10" in url

    def test_builds_solr_filters_from_structured_params(self):
        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(ISOLATES_RESPONSE)) as u:
            pathogen_isolates(
                organism="Salmonella enterica",
                geo="China",
                serovar="Enteritidis",
                year_from=2025,
                year_to=2026,
                has_ast=True,
            )

        url = u.call_args.args[0].full_url
        import urllib.parse as _up

        fq = _up.parse_qs(url.split("?", 1)[1])["fq"][0]
        assert 'taxgroup_name:"Salmonella enterica"' in fq
        assert "geo_loc_name:China" in fq
        assert "serovar:Enteritidis" in fq
        assert "collection_date:[2025-01-01 TO 2026-12-31]" in fq
        assert "AST_phenotypes:*" in fq
        assert " AND " in fq

    def test_raw_fq_passthrough(self):
        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(ISOLATES_RESPONSE)) as u:
            pathogen_isolates(fq='epi_type:clinical AND AMR_genotypes:blaCTX*')

        url = u.call_args.args[0].full_url
        assert "epi_type%3Aclinical" in url

    def test_no_filters_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            pathogen_isolates()

    def test_success_false_raises_runtimeerror(self):
        bad = {"success": False, "error": "cannot retrieve from the database"}
        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(bad)):
            with pytest.raises(RuntimeError, match="cannot retrieve"):
                pathogen_isolates(organism="Salmonella")

    def test_network_error_raises_runtimeerror(self):
        import urllib.error

        with patch(f"{_MOD}.urlopen", side_effect=urllib.error.URLError("down")):
            with pytest.raises(RuntimeError, match="NCBI pathogens"):
                pathogen_isolates(organism="Salmonella")

    def test_max_results_capped(self):
        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(ISOLATES_RESPONSE)) as u:
            pathogen_isolates(organism="Salmonella", max_results=5000)

        assert "limit=100" in u.call_args.args[0].full_url


class TestPathogenAmrElements:
    def test_returns_amr_elements(self):
        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(AMR_RESPONSE)) as u:
            result = pathogen_amr_elements(
                organism="Salmonella enterica", element="pagK", max_results=5
            )

        assert result["total"] == 16434388
        el = result["elements"][0]
        assert el["symbol"] == "pagK"
        assert el["length_bp"] == 66

        url = u.call_args.args[0].full_url
        assert "collection=amr" in url
        assert "element_symbol%3ApagK" in url

    def test_requires_organism(self):
        with pytest.raises(ValueError, match="organism"):
            pathogen_amr_elements()


class TestHandler:
    def test_handler_isolates_action(self):
        from hermes_bacmap.tools import ncbi_pathogen as handler

        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(ISOLATES_RESPONSE)):
            out = handler({"action": "isolates", "organism": "Salmonella enterica"})

        d = json.loads(out)
        assert d["total"] == 768

    def test_handler_amr_action(self):
        from hermes_bacmap.tools import ncbi_pathogen as handler

        with patch(f"{_MOD}.urlopen", side_effect=_fake_urlopen(AMR_RESPONSE)):
            out = handler({"action": "amr", "organism": "Salmonella enterica", "element": "pagK"})

        d = json.loads(out)
        assert d["elements"][0]["symbol"] == "pagK"

    def test_handler_error_returns_error_json(self):
        from hermes_bacmap.tools import ncbi_pathogen as handler

        out = handler({"action": "isolates"})
        assert "error" in json.loads(out)
