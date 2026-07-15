#!/usr/bin/env python3
"""Import strain metadata and/or lab results from TSV files into SQLite.

Usage:
    # Import metadata
    python scripts/import_meta.py --metadata samples_meta.tsv

    # Import lab results
    python scripts/import_meta.py --lab-results lab_results.tsv

    # Import both
    python scripts/import_meta.py --metadata samples_meta.tsv --lab-results lab_results.tsv

    # Add single record interactively
    python scripts/import_meta.py --add SAM-TYP-001 patient_name=张三 province=北京
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import ROOT
sys.path.insert(0, str(ROOT / "src"))

from hermes_bacmap.services.strain_metadata import StrainMetadataService
from hermes_bacmap.services.lab_results import LabResultService

DB_PATH = ROOT / "data" / "hermes_bacmap.sqlite"


def import_metadata(tsv_path: str) -> int:
    with StrainMetadataService(DB_PATH) as svc:
        count = svc.import_tsv(tsv_path)
        print(f"  ✅ {count} metadata records imported")
        return count


def import_lab_results(tsv_path: str) -> int:
    with LabResultService(DB_PATH) as svc:
        count = svc.import_tsv(tsv_path)
        print(f"  ✅ {count} lab results imported")
        return count


def add_single(strain_id: str, fields: list[str]) -> None:
    data: dict[str, str] = {}
    for f in fields:
        if "=" in f:
            k, v = f.split("=", 1)
            data[k] = v

    if not data:
        print("  ❌ No fields provided. Use key=value format.")
        sys.exit(1)

    with StrainMetadataService(DB_PATH) as svc:
        meta = svc.upsert(strain_id, data)
        print(f"  ✅ {strain_id}: saved {len(data)} fields")
        for k, v in meta.to_dict().items():
            if k in data:
                print(f"     {k} = {v}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import strain metadata / lab results")
    parser.add_argument("--metadata", help="TSV file with strain metadata")
    parser.add_argument("--lab-results", help="TSV file with lab results")
    parser.add_argument("--add", nargs="+", metavar="STRAIN_ID key=val key=val...",
                        help="Add single metadata record")
    args = parser.parse_args()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if args.add:
        strain_id = args.add[0]
        fields = args.add[1:]
        add_single(strain_id, fields)
        return 0

    if args.metadata:
        import_metadata(args.metadata)

    if args.lab_results:
        import_lab_results(args.lab_results)

    if not args.metadata and not args.lab_results and not args.add:
        parser.print_help()
        return 1

    print(f"\n  Database: {DB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
