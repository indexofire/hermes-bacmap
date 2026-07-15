#!/usr/bin/env python3
"""Download Gold standard FASTQ from ENA (no SRA Toolkit required).

Usage:
    python scripts/download_gold_standard.py [--dry-run] [--only SAM-TYP-001,SAM-NEW-006]

Reads tests/fixtures/gold_standard/salmonella/gold_standard.csv,
queries ENA filereport API for each SRR, downloads FASTQ via HTTPS,
verifies MD5, and updates CSV paths.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from _common import ROOT

CSV_PATH = ROOT / "tests/fixtures/gold_standard/salmonella/gold_standard.csv"
DATA_DIR = ROOT / "tests/fixtures/gold_standard/salmonella/data"
ENA_API = "https://www.ebi.ac.uk/ena/portal/api/filereport"
ENA_HTTPS_BASE = "https://ftp.sra.ebi.ac.uk/vol1/fastq/"


def ena_filereport(srr: str) -> dict | None:
    url = f"{ENA_API}?accession={srr}&result=read_run&fields=run_accession,fastq_ftp,fastq_md5,fastq_bytes,library_layout&format=json"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
        return data[0] if data else None
    except Exception as e:
        print(f"  ✗ ENA API error for {srr}: {e}", file=sys.stderr)
        return None


def md5sum(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> bool:
    try:
        subprocess.run(
            ["aria2c", "-x", "16", "-s", "16", "--console-log-level=error",
             "-d", str(dest.parent), "-o", dest.name, url],
            check=True,
            capture_output=True,
        )
        return True
    except FileNotFoundError:
        try:
            urllib.request.urlretrieve(url, dest)
            return True
        except Exception as e:
            print(f"  ✗ Download failed (no aria2c, urllib fallback): {e}", file=sys.stderr)
            return False
    except subprocess.CalledProcessError as e:
        print(f"  ✗ aria2c failed: {e.stderr.decode()[:200]}", file=sys.stderr)
        return False


def process_strain(row: dict, dry_run: bool = False) -> dict | None:
    strain_id = row["strain_id"]
    srr = row["sra_accession"]

    if not srr or srr.startswith("PENDING"):
        print(f"  ⊘ {strain_id}: SRR pending, skipped")
        return None

    print(f"\n=== {strain_id} ({srr}) — {row['serovar']} ===")

    report = ena_filereport(srr)
    if not report:
        return None

    ftp_paths = report.get("fastq_ftp", "").split(";")
    md5s = report.get("fastq_md5", "").split(";")
    sizes = report.get("fastq_bytes", "").split(";")
    layout = report.get("library_layout", "PAIRED")

    ftp_paths = [p for p in ftp_paths if p.strip()]
    md5s = [m for m in md5s if m.strip()]
    sizes = [s for s in sizes if s.strip()]

    if not ftp_paths:
        print(f"  ✗ No FASTQ available on ENA for {srr}")
        return None

    total_mb = sum(int(s) for s in sizes) / 1e6
    print(f"  Layout: {layout}, Files: {len(ftp_paths)}, Total: {total_mb:.0f} MB")

    strain_dir = DATA_DIR / strain_id
    strain_dir.mkdir(parents=True, exist_ok=True)

    files_to_verify = []

    for i, (ftp_path, expected_md5, size_str) in enumerate(zip(ftp_paths, md5s, sizes)):
        https_url = f"https://{ftp_path}"

        if len(ftp_paths) == 1 and layout == "SINGLE":
            dest_name = f"{strain_id}_R1.fastq.gz"
        elif len(ftp_paths) == 2:
            dest_name = f"{strain_id}_R{i+1}.fastq.gz"
        else:
            dest_name = f"{strain_id}_file{i+1}.fastq.gz"

        dest = strain_dir / dest_name
        size_mb = int(size_str) / 1e6

        if dest.exists() and dest.stat().st_size == int(size_str):
            actual_md5 = md5sum(dest)
            if actual_md5 == expected_md5:
                print(f"  ✓ {dest_name} already downloaded (MD5 verified, {size_mb:.0f} MB)")
                files_to_verify.append((dest, dest_name))
                continue
            else:
                print(f"  ! {dest_name} exists but MD5 mismatch, re-downloading...")

        if dry_run:
            print(f"  [DRY RUN] Would download {dest_name} ({size_mb:.0f} MB)")
            files_to_verify.append((dest, dest_name))
            continue

        print(f"  ↓ Downloading {dest_name} ({size_mb:.0f} MB)...", end=" ", flush=True)
        t0 = time.time()
        if download(https_url, dest):
            elapsed = time.time() - t0
            speed = size_mb / elapsed if elapsed > 0 else 0
            actual_md5 = md5sum(dest)
            if actual_md5 == expected_md5:
                print(f"✓ MD5 verified ({elapsed:.0f}s, {speed:.1f} MB/s)")
                files_to_verify.append((dest, dest_name))
            else:
                print("✗ MD5 mismatch!")
                print(f"    expected: {expected_md5}")
                print(f"    actual:   {actual_md5}")
                dest.unlink(missing_ok=True)
        else:
            print("FAILED")

    if files_to_verify:
        updated = dict(row)
        if len(files_to_verify) >= 1:
            updated["fastq_r1_path"] = str(files_to_verify[0][0].relative_to(ROOT))
        if len(files_to_verify) >= 2:
            updated["fastq_r2_path"] = str(files_to_verify[1][0].relative_to(ROOT))
        return updated

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Gold standard FASTQ from ENA")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded")
    parser.add_argument("--only", type=str, help="Comma-separated strain_ids to download")
    args = parser.parse_args()

    with CSV_PATH.open() as f:
        rows = list(csv.DictReader(f))
        header = list(rows[0].keys())

    only_set = set(args.only.split(",")) if args.only else None

    updated_rows = []
    downloaded = 0
    for row in rows:
        if only_set and row["strain_id"] not in only_set:
            updated_rows.append(row)
            continue
        result = process_strain(row, dry_run=args.dry_run)
        if result:
            updated_rows.append(result)
            if result.get("fastq_r1_path"):
                downloaded += 1
        else:
            updated_rows.append(row)

    if not args.dry_run and downloaded > 0:
        with CSV_PATH.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(updated_rows)
        print(f"\n✓ CSV updated with FASTQ paths for {downloaded} strains")

    print(f"\nDone. {downloaded}/{len(rows)} strains have FASTQ files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
