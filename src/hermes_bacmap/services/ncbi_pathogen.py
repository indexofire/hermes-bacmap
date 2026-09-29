"""NCBI Pathogen Detection connector — surveillance isolates and AMR elements.

Queries the Isolates Browser's own backend (pathogens-srv, publicly
reachable, no key, rate-limit politely ≤1 req/s). Contract verified by live
requests: action=retrieve with collection=isolates (surveillance) or
collection=amr (MicroBIGG-E AMR/virulence elements), SOLR ``fq`` filters,
``fl`` field list, ``start``/``limit`` paging, response rooted at
``ngout.data.content`` / ``ngout.data.totalCount``.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

_BASE = "https://www.ncbi.nlm.nih.gov/pathogens/pathogens-srv/"
_USER_AGENT = "hermes-bacmap/0.5 (pathogen genome analysis; contact: indexofire@gmail.com)"
_TIMEOUT_S = 60
_MAX_LIMIT = 100

_ISOLATE_FIELDS = (
    "target_acc,biosample_acc,taxgroup_name,scientific_name,serovar,strain,"
    "geo_loc_name,isolation_source,collection_date,epi_type,"
    "AST_phenotypes,AMR_genotypes,virulence_genotypes"
)
_AMR_FIELDS = (
    "target_acc,element_name,element_symbol,element_length,"
    "closest_reference_name,scientific_name,geo_loc_name"
)


def pathogen_isolates(
    organism: str = "",
    geo: str = "",
    serovar: str = "",
    year_from: int = 0,
    year_to: int = 0,
    has_ast: bool = False,
    fq: str = "",
    max_results: int = 20,
) -> dict[str, Any]:
    filters: list[str] = []
    if organism:
        filters.append(f'taxgroup_name:"{organism}"')
    if geo:
        filters.append(f"geo_loc_name:{geo}")
    if serovar:
        filters.append(f"serovar:{serovar}")
    if year_from or year_to:
        start = f"{year_from}-01-01" if year_from else "*"
        end = f"{year_to}-12-31" if year_to else "*"
        filters.append(f"collection_date:[{start} TO {end}]")
    if has_ast:
        filters.append("AST_phenotypes:*")

    query = " AND ".join(filters) if filters else fq.strip()
    if not query:
        raise ValueError("provide at least one filter (organism/geo/serovar/year/has_ast) or fq")

    data = _retrieve("isolates", query, _ISOLATE_FIELDS, max_results)
    isolates = [
        {
            "target_acc": r.get("target_acc", ""),
            "biosample_acc": r.get("biosample_acc", ""),
            "organism": r.get("taxgroup_name", ""),
            "scientific_name": r.get("scientific_name", ""),
            "serovar": r.get("serovar", ""),
            "strain": r.get("strain", ""),
            "geo": r.get("geo_loc_name", ""),
            "isolation_source": r.get("isolation_source", ""),
            "collection_date": r.get("collection_date", ""),
            "epi_type": r.get("epi_type", ""),
            "ast": r.get("AST_phenotypes") or [],
            "amr_genotypes": r.get("AMR_genotypes") or [],
            "virulence_genotypes": r.get("virulence_genotypes") or [],
        }
        for r in data["content"]
    ]
    return {
        "source": "ncbi_pathogen_detection",
        "total": data["totalCount"],
        "returned": len(isolates),
        "query": query,
        "isolates": isolates,
    }


def pathogen_amr_elements(
    organism: str = "",
    element: str = "",
    geo: str = "",
    max_results: int = 20,
) -> dict[str, Any]:
    if not organism:
        raise ValueError("organism (taxgroup_name) is required for AMR element queries")

    filters = [f'taxgroup_name:"{organism}"']
    if element:
        filters.append(f"element_symbol:{element}")
    if geo:
        filters.append(f"geo_loc_name:{geo}")
    query = " AND ".join(filters)

    data = _retrieve("amr", query, _AMR_FIELDS, max_results)
    elements = [
        {
            "target_acc": r.get("target_acc", ""),
            "symbol": r.get("element_symbol", ""),
            "name": r.get("element_name", ""),
            "length_bp": r.get("element_length", 0),
            "closest_reference": r.get("closest_reference_name", ""),
            "organism": r.get("scientific_name", ""),
            "geo": r.get("geo_loc_name", ""),
        }
        for r in data["content"]
    ]
    return {
        "source": "ncbi_microbigge",
        "total": data["totalCount"],
        "returned": len(elements),
        "query": query,
        "elements": elements,
    }


def _retrieve(collection: str, fq: str, fl: str, max_results: int) -> dict[str, Any]:
    import urllib.parse

    limit = max(1, min(int(max_results), _MAX_LIMIT))
    params = urllib.parse.urlencode(
        {
            "action": "retrieve",
            "collection": collection,
            "fq": fq,
            "fl": fl,
            "start": 0,
            "limit": limit,
            "sort": '[{"property":"collection_date","direction":"DESC"}]',
        }
    )
    url = f"{_BASE}?{params}"
    req = Request(url, headers={"User-Agent": _USER_AGENT})

    try:
        with urlopen(req, timeout=_TIMEOUT_S) as resp:
            body = json.loads(resp.read().decode())
    except OSError as e:
        raise RuntimeError(f"NCBI pathogens request failed: {e}") from e

    if not body.get("success"):
        raise RuntimeError(
            f"NCBI pathogens error: {body.get('error', 'unknown')} (check filter syntax)"
        )
    data = body.get("ngout", {}).get("data") or {}
    return {
        "content": list(data.get("content", [])),
        "totalCount": int(data.get("totalCount", 0)),
    }
