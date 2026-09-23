#!/usr/bin/env python3
"""Expand genus-level groups to species-level using Entrez esearch Subtree.

For each genus-rank entry in taxonomy_verified.tsv, finds the species
present in the panel (from metadata.tsv), then queries Entrez for each
species' authoritative taxid via Subtree search.
"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
RATE_LIMIT_SEC = 0.4
MAX_RETRIES = 3


def _entrez_json(endpoint: str, params: dict) -> dict:
    url = f"{EUTILS}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "hermes-bacmap/0.5"})
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(5 * (attempt + 1))
            else:
                return {}
    return {}


def get_species_taxid(scientific_name: str) -> tuple[int, str, str, str]:
    result = _entrez_json("esearch.fcgi", {
        "db": "taxonomy", "term": scientific_name, "retmode": "json",
    })
    ids = result.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return (0, "", "", "")
    taxid = int(ids[0])
    time.sleep(RATE_LIMIT_SEC)
    summary = _entrez_json("esummary.fcgi", {
        "db": "taxonomy", "id": str(taxid), "retmode": "json",
    }).get("result", {}).get(str(taxid), {})
    return (
        taxid,
        summary.get("rank", ""),
        summary.get("lineage", ""),
        summary.get("division", ""),
    )


def main() -> int:
    panel = ROOT / "data/db/refseq_panel"
    verified = panel / "taxonomy_verified.tsv"
    cache_path = panel / "entrez_species_cache.json"

    cache: dict = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text())

    lines = verified.read_text().splitlines()
    rows = [ln.split("\t") for ln in lines[1:]]

    panel_species: dict[str, set[str]] = {}
    with (panel / "metadata.tsv").open() as fh:
        for rec in csv.DictReader(fh, delimiter="\t"):
            species_name = rec.get("species", "")
            for prefix, group in [
        ("Escherichia coli", "Escherichia_coli_Shigella"), ("Shigella", "Escherichia_coli_Shigella"),
            ]:
                if species_name.startswith(prefix):
                    panel_species.setdefault(group, set()).add(species_name)
                    break
            else:
                first_word = species_name.split()[0] if species_name.split() else ""
                if first_word:
                    panel_species.setdefault(first_word, set()).add(species_name)

    expanded = []
    genus_expanded = 0
    for row in rows:
        group, sci_name, taxid, rank, lineage, division = row
        expanded.append(row)
        if rank != "genus":
            continue

        genus_word = sci_name.split()[0]
        panel_under = set()
        for g2, species_set in panel_species.items():
            if g2 == group or genus_word.lower() in g2.lower():
                panel_under |= species_set
        if not panel_under:
            for s in panel_species.get(sci_name, set()):
                panel_under.add(s)

        genus_expanded += 1
        print(f"  {sci_name} (genus, taxid={taxid}): {len(panel_under)} panel species")
        for sp in sorted(panel_under):
            sp_name = " ".join(sp.split()[:2])
            if sp_name in cache:
                c = cache[sp_name]
                expanded.append([group, sp_name, str(c["taxid"]), c["rank"], c["lineage"], c["division"]])
            else:
                time.sleep(RATE_LIMIT_SEC)
                tid, rk, lin, div = get_species_taxid(sp_name)
                cache[sp_name] = {"taxid": tid, "rank": rk, "lineage": lin, "division": div}
                cache_path.write_text(json.dumps(cache, indent=2))
                expanded.append([group, sp_name, str(tid), rk, lin, div])
                print(f"    → {sp_name}: taxid={tid}")

    out = panel / "taxonomy_expanded.tsv"
    with out.open("w") as fh:
        fh.write("group\tscientific_name\ttaxid\trank\tlineage\tdivision\n")
        for row in expanded:
            fh.write("\t".join(row) + "\n")

    n_genus = sum(1 for r in expanded if r[3] == "genus")
    n_species = sum(1 for r in expanded if r[3] == "species")
    print(f"\n✓ {out}: {len(expanded)} rows ({n_genus} genus + {n_species} species)")
    print(f"  {genus_expanded} genus groups expanded to species level")
    return 0


if __name__ == "__main__":
    sys.exit(main())
