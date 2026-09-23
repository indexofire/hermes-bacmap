#!/usr/bin/env python3
"""Query NCBI Entrez taxonomy for authoritative taxid by Latin name.

Reads FTP tracked-group names, converts to scientific names, queries
Entrez for the current NCBI taxid. Results are cached to a JSON file
so re-runs skip already-verified entries (NCBI rate limit: 3 req/s).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
RATE_LIMIT_SEC = 0.4
MAX_RETRIES = 3
RETRY_WAIT = 5

from download_validation_genomes import fetch_tracked_groups  # noqa: E402
from download_db_refseq_panel import bacterial_groups, group_to_queries  # noqa: E402


def _entrez_get(endpoint: str, params: dict) -> dict:
    url = f"{EUTILS}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "hermes-bacmap/0.5"})
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_WAIT * (attempt + 1)
                print(f"    retry {attempt + 1}/{MAX_RETRIES} after {wait}s ({e})")
                time.sleep(wait)
            else:
                raise
    return {}


def esearch_taxid(name: str) -> int | None:
    result = _entrez_get("esearch.fcgi", {
        "db": "taxonomy", "term": name, "retmode": "json",
    })
    ids = result.get("esearchresult", {}).get("idlist", [])
    return int(ids[0]) if ids else None


def esummary_lineage(taxid: int) -> dict:
    result = _entrez_get("esummary.fcgi", {
        "db": "taxonomy", "id": str(taxid), "retmode": "json",
    })
    return result.get("result", {}).get(str(taxid), {})


def load_cache(cache_path: Path) -> dict:
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_cache(cache_path: Path, cache: dict) -> None:
    cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "data/db/refseq_panel/taxonomy_verified.tsv",
    )
    args = parser.parse_args(argv)

    cache_path = args.out.parent / "entrez_cache.json"
    cache = load_cache(cache_path)

    tracked = fetch_tracked_groups()
    if not tracked:
        print("✗ 无法获取 FTP 追踪清单")
        return 1
    groups = bacterial_groups(tracked)
    print(f"追踪病原组: {len(groups)}，缓存已有 {len(cache)} 条")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, str, str, str, str, str]] = []

    for group in groups:
        for name in group_to_queries(group):
            if name in cache:
                c = cache[name]
                results.append((group, name, str(c.get("taxid", "")), c.get("rank", ""), c.get("lineage", ""), c.get("division", "")))
                continue

            try:
                time.sleep(RATE_LIMIT_SEC)
                taxid = esearch_taxid(name)
                time.sleep(RATE_LIMIT_SEC)
                if taxid:
                    summary = esummary_lineage(taxid)
                    entry = {
                        "taxid": taxid,
                        "rank": summary.get("rank", ""),
                        "lineage": summary.get("lineage", ""),
                        "division": summary.get("division", ""),
                        "scientific_name": summary.get("scientificname", name),
                    }
                else:
                    entry = {"taxid": None, "rank": "", "lineage": "", "division": "", "scientific_name": name}

                cache[name] = entry
                save_cache(cache_path, cache)
                results.append((group, name, str(entry.get("taxid") or ""), entry.get("rank", ""), entry.get("lineage", ""), entry.get("division", "")))
                status = f"taxid={taxid}" if taxid else "NOT FOUND"
                print(f"  ✓ {name} → {status}")
            except Exception as e:
                print(f"  ⚠ {name}: {e}")
                results.append((group, name, "", "", "", ""))

    with args.out.open("w") as fh:
        fh.write("group\tscientific_name\ttaxid\trank\tlineage\tdivision\n")
        for row in results:
            fh.write("\t".join(row) + "\n")

    found = sum(1 for r in results if r[2])
    print(f"\n✓ Entrez taxonomy: {found}/{len(results)} verified → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
