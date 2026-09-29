"""Literature connector — Europe PMC search (free REST, no API key).

Gives the agent the verification step of the discovery loop: after finding
a putative novel marker, search the literature for prior evidence. Europe
PMC covers PubMed/MEDLINE plus life-science preprints.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any
from urllib.request import urlopen

_EPMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_ABSTRACT_MAX = 500
_TIMEOUT_S = 30


def lit_search(query: str, max_results: int = 5) -> dict[str, Any]:
    query = query.strip()
    if not query:
        raise ValueError("query must be non-empty")
    max_results = max(1, min(int(max_results), 25))

    params = urllib.parse.urlencode(
        {
            "query": query,
            "format": "json",
            "pageSize": max_results,
            "resultType": "core",
        }
    )
    url = f"{_EPMC_URL}?{params}"

    try:
        with urlopen(url, timeout=_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode())
    except OSError as e:
        raise RuntimeError(f"Europe PMC request failed: {e}") from e

    if "resultList" not in data or "result" not in data["resultList"]:
        raise RuntimeError(f"Europe PMC unexpected response shape: {list(data)[:5]}")

    papers = [_to_paper(r) for r in data["resultList"]["result"]]
    return {
        "query": query,
        "source": "europepmc",
        "total_hits": data.get("hitCount", 0),
        "papers": papers,
    }


def _to_paper(r: dict[str, Any]) -> dict[str, Any]:
    title = (r.get("title") or "").strip()
    journal = (r.get("journalTitle") or "").strip()
    year = str(r.get("pubYear") or "")
    authors = (r.get("authorString") or "").strip()

    ids = []
    if r.get("pmid"):
        ids.append(f"PMID:{r['pmid']}")
    elif r.get("id"):
        ids.append(f"{r.get('source', 'PMC')}:{r['id']}")

    citation = f"{authors}. {title}."
    if journal:
        citation += f" {journal}"
    if year:
        citation += f" ({year})."
    if ids:
        citation += " " + ids[0]

    return {
        "title": title,
        "citation": citation,
        "abstract": (r.get("abstractText") or "")[:_ABSTRACT_MAX],
        "doi": r.get("doi") or "",
        "pmid": r.get("pmid") or "",
        "pmcid": r.get("pmcid") or "",
        "journal": journal,
        "year": year,
        "authors": authors,
    }
