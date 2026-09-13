#!/usr/bin/env python3
"""Build the local cgMLST reference library for trace-back projection.

For each reference assembly contigs FASTA belonging to the requested species
(discovered via ``workflows/bacmap/config/samples.tsv`` cross-referenced with
``data/assemblies/<sample>/contigs.fasta``), runs
``gmlst typing cgmlst -s <scheme> --format tsv`` once per assembly and merges
the per-sample TSVs into one multi-sample ``reference_profiles.tsv`` plus a
``reference_meta.json`` recording provenance.

Initial scope: **Salmonella-only**. The 6 real Salmonella assemblies under
``data/assemblies/`` (SAM-ENT-003/004, SAM-INF-005, SAM-NEW-006,
SAM-TYP-001/002) are the seed reference set. DEC/Shigella/Vpara reference
profiles are PENDING until their assemblies exist — invoking this script for
those species writes a ``reference_meta.json`` flagged
``status="pending_assemblies"`` and exits non-zero with a clear message so an
operator knows the library is not yet populated for that species.

NO runtime network: the scheme is assumed already vendored by
``workflows/bacmap/scripts/vendor_cgmlst_schemes.py`` (todo 3). This script
only consumes the vendored scheme via the gmlst binary.

Usage::

    python scripts/build_cgmlst_reference.py \\
        --species salmonella --scheme senterica_2
    # -> data/reference/cgmlst/salmonella/reference_profiles.tsv
    #    data/reference/cgmlst/salmonella/reference_meta.json

    python scripts/build_cgmlst_reference.py \\
        --species salmonella --scheme senterica_2 \\
        --output-dir /tmp/cgmlst-ref --threads 4
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from _common import ROOT, SAMPLES_TSV

from hermes_bacmap.utils import parse_cgmlst_profiles

DEFAULT_ASSEMBLIES_DIR = ROOT / "data" / "assemblies"
DEFAULT_REFERENCE_ROOT = ROOT / "data" / "reference" / "cgmlst"
DEFAULT_GMLST_BIN = str(ROOT / ".pixi" / "envs" / "default" / "bin" / "gmlst")
DEFAULT_THREADS = 4
DEFAULT_TIMEOUT_S = 3600  # cgMLST on 3002 loci + minimap2 can take several min/sample.


def _resolve_gmlst_bin(explicit: str | None) -> str:
    """Locate the gmlst binary: explicit arg > pixi env default > PATH lookup."""
    if explicit:
        return explicit
    if Path(DEFAULT_GMLST_BIN).exists():
        return DEFAULT_GMLST_BIN
    found = shutil.which("gmlst")
    if not found:
        raise FileNotFoundError(
            "gmlst binary not found: pass --gmlst-bin, install via `pixi install`, "
            f"or ensure gmlst is on PATH (default tried: {DEFAULT_GMLST_BIN})"
        )
    return found


def _gmlst_version(gmlst_bin: str) -> str:
    """Best-effort gmlst version string for meta provenance."""
    try:
        out = subprocess.run(
            [gmlst_bin, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        combined = (out.stdout + out.stderr).strip()
        return combined.splitlines()[0] if combined else "unknown"
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"  ! could not determine gmlst version: {exc}", file=sys.stderr)
        return "unknown"


def _read_samples_tsv() -> list[dict[str, str]]:
    """Load samples.tsv into a list of row dicts (sample, species, R1, R2)."""
    if not SAMPLES_TSV.exists():
        return []
    rows: list[dict[str, str]] = []
    for line in SAMPLES_TSV.read_text().splitlines():
        if not line.strip() or line.startswith("sample\t"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append({"sample": parts[0], "species": parts[1]})
    return rows


def discover_reference_assemblies(
    species: str,
    assemblies_dir: Path,
) -> list[tuple[str, Path]]:
    """Return ``(sample_id, contigs_fasta)`` pairs for the requested species.

    Cross-references samples.tsv (species column, case-insensitive) with
    ``<assemblies_dir>/<sample>/contigs.fasta`` on disk. A sample listed in
    samples.tsv but missing its assembly directory is silently skipped — the
    caller surfaces the count via the final meta.
    """
    species_lower = species.lower()
    pairs: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for row in _read_samples_tsv():
        if row["species"].lower() != species_lower:
            continue
        sample = row["sample"]
        if sample in seen:
            continue
        seen.add(sample)
        contigs = assemblies_dir / sample / "contigs.fasta"
        if contigs.exists():
            pairs.append((sample, contigs))
    # Deterministic order so two runs produce byte-identical output ordering.
    pairs.sort(key=lambda p: p[0])
    return pairs


def _run_one_sample(
    gmlst_bin: str,
    scheme: str,
    sample_id: str,
    contigs: Path,
    out_tsv: Path,
    threads: int,
    timeout: int,
) -> tuple[bool, str]:
    """Invoke gmlst typing cgmlst on one assembly. Returns (ok, message).

    Writes the per-sample TSV to ``out_tsv``. On failure returns ``(False, err)``
    and removes any partial output so downstream merge never sees a half-file.
    """
    cmd = [
        gmlst_bin,
        "typing",
        "cgmlst",
        "-s",
        scheme,
        "--format",
        "tsv",
        "-t",
        str(threads),
        "-o",
        str(out_tsv),
        str(contigs),
    ]
    print(f"  $ {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        out_tsv.unlink(missing_ok=True)
        return (False, f"timeout after {timeout}s")
    except OSError as exc:
        out_tsv.unlink(missing_ok=True)
        return (False, f"os error: {exc}")

    if result.returncode != 0:
        out_tsv.unlink(missing_ok=True)
        stderr_tail = (result.stderr or "").strip().splitlines()
        tail = stderr_tail[-1] if stderr_tail else f"exit {result.returncode}"
        return (False, tail)

    if not out_tsv.exists() or out_tsv.stat().st_size == 0:
        return (False, "gmlst produced no output")
    return (True, "")


def _read_header_and_row(tsv_path: Path) -> tuple[str, str]:
    """Return (header_line, first_data_line) from a per-sample gmlst TSV.

    Raises ``ValueError`` if the file does not contain at least a header and
    one data row — this is the contract every successful per-sample run must
    satisfy for the merge to be well-defined.
    """
    lines = tsv_path.read_text().splitlines()
    # Skip blank trailing lines (defensive — gmlst does not emit them).
    lines = [ln for ln in lines if ln.strip()]
    if len(lines) < 2:
        raise ValueError(f"{tsv_path}: expected header + 1 data row, found {len(lines)} line(s)")
    return (lines[0], lines[1])


def merge_profiles(
    per_sample: list[tuple[str, Path]],
    output_tsv: Path,
) -> tuple[int, list[str], list[tuple[str, str]]]:
    """Merge per-sample TSVs into one multi-sample ``output_tsv``.

    All per-sample TSVs share the same scheme and therefore the same locus
    header (cgMLST schemes have a fixed locus set). This function asserts the
    headers are byte-identical, writes the shared header once, then appends each
    sample's data row.

    Returns ``(n_loci, merged_sample_ids, failures)`` where ``failures`` is a
    list of ``(sample_id, reason)`` for samples whose TSV was missing or
    malformed at merge time.
    """
    canonical_header: str | None = None
    data_rows: list[str] = []
    merged: list[str] = []
    failures: list[tuple[str, str]] = []

    for sample_id, tsv_path in per_sample:
        if not tsv_path.exists():
            failures.append((sample_id, "per-sample TSV missing"))
            continue
        try:
            header, row = _read_header_and_row(tsv_path)
        except ValueError as exc:
            failures.append((sample_id, str(exc)))
            continue
        if canonical_header is None:
            canonical_header = header
        elif header != canonical_header:
            # A scheme with a stable locus set must yield identical headers.
            # A divergence indicates a mid-run scheme change or corruption.
            failures.append((sample_id, "header mismatch — scheme drift suspected"))
            continue
        data_rows.append(row)
        merged.append(sample_id)

    assert canonical_header is not None, "merge_profiles called with no usable rows"
    output_tsv.parent.mkdir(parents=True, exist_ok=True)
    output_tsv.write_text("\n".join([canonical_header, *data_rows]) + "\n")

    locus_cols = canonical_header.split("\t")[3:]  # drop File/Scheme/ST
    return (len(locus_cols), merged, failures)


def _write_meta(
    meta_path: Path,
    scheme: str,
    n_loci: int,
    source_genomes: list[str],
    gmlst_version: str,
    status: str,
    failures: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Write reference_meta.json. Returns the dict that was written."""
    meta = {
        "scheme": scheme,
        "n_loci": n_loci,
        "source_genomes": source_genomes,
        "built_at": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "gmlst_version": gmlst_version,
        "status": status,
    }
    if failures:
        meta["failures"] = [{"sample": s, "reason": r} for s, r in sorted(failures)]
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    return meta


def build_reference(
    species: str,
    scheme: str,
    output_dir: Path,
    assemblies_dir: Path,
    gmlst_bin: str,
    threads: int,
    timeout: int,
) -> int:
    """Top-level driver. Returns a process exit code (0 success, 1 failure)."""
    print(f"=== Building cgMLST reference for {species} (scheme={scheme}) ===")
    print(f"output dir:   {output_dir}")
    print(f"assemblies:   {assemblies_dir}")
    print(f"gmlst binary: {gmlst_bin}")
    output_dir.mkdir(parents=True, exist_ok=True)

    profiles_tsv = output_dir / "reference_profiles.tsv"
    meta_path = output_dir / "reference_meta.json"
    gmlst_ver = _gmlst_version(gmlst_bin)

    assemblies = discover_reference_assemblies(species, assemblies_dir)
    if not assemblies:
        # No reference assemblies available yet (e.g. DEC/Shigella/Vpara).
        # Record the pending state so downstream tooling can detect it.
        msg = (
            f"no reference assemblies found for species={species!r} under "
            f"{assemblies_dir}; reference library is PENDING for this species"
        )
        print(f"❌ {msg}", file=sys.stderr)
        _write_meta(
            meta_path,
            scheme=scheme,
            n_loci=0,
            source_genomes=[],
            gmlst_version=gmlst_ver,
            status="pending_assemblies",
        )
        print(f"  wrote pending marker: {meta_path}")
        return 1

    print(f"found {len(assemblies)} reference assembly/assemblies:")
    for sid, contigs in assemblies:
        print(f"  - {sid}: {contigs}")

    # Per-sample profiling into a temp dir; merge at the end.
    run_failures: list[tuple[str, str]] = []
    per_sample_outputs: list[tuple[str, Path]] = []
    with tempfile.TemporaryDirectory(prefix="cgmlst-ref-") as tmp:
        tmp_dir = Path(tmp)
        for sample_id, contigs in assemblies:
            out_tsv = tmp_dir / f"{sample_id}.cgmlst.tsv"
            ok, msg = _run_one_sample(
                gmlst_bin, scheme, sample_id, contigs, out_tsv, threads, timeout
            )
            if ok:
                print(f"  ✓ {sample_id} profiled")
                per_sample_outputs.append((sample_id, out_tsv))
            else:
                print(f"  ✗ {sample_id} failed: {msg}", file=sys.stderr)
                run_failures.append((sample_id, msg))

        if not per_sample_outputs:
            print(
                f"❌ all {len(assemblies)} gmlst runs failed; no reference profiles produced",
                file=sys.stderr,
            )
            _write_meta(
                meta_path,
                scheme=scheme,
                n_loci=0,
                source_genomes=[],
                gmlst_version=gmlst_ver,
                status="gmlst_failed",
                failures=run_failures,
            )
            return 1

        # Merge happens inside the temp dir context so per-sample files exist.
        n_loci, merged, merge_failures = merge_profiles(per_sample_outputs, profiles_tsv)
        all_failures = run_failures + merge_failures

    # Integrity check: the merged TSV must round-trip through the todo-1 parser.
    text = profiles_tsv.read_text()
    profiles = parse_cgmlst_profiles(text)
    if len(profiles) != len(merged):
        print(
            f"⚠ merged TSV has {len(merged)} rows but parser returned "
            f"{len(profiles)} profiles; check for blank/malformed rows",
            file=sys.stderr,
        )

    status = "built" if not all_failures else "partial"
    _write_meta(
        meta_path,
        scheme=scheme,
        n_loci=n_loci,
        source_genomes=merged,
        gmlst_version=gmlst_ver,
        status=status,
        failures=all_failures or None,
    )

    print(f"\n✓ wrote {profiles_tsv} ({len(merged)} samples, {n_loci} loci)")
    print(f"✓ wrote {meta_path} (status={status})")
    if all_failures:
        print(f"  {len(all_failures)} sample(s) failed; see meta.failures")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the local cgMLST reference library "
            "(data/reference/cgmlst/<species>/). Runs gmlst typing cgmlst on "
            "each reference assembly for the requested species and merges the "
            "per-sample profiles into one multi-sample TSV. Build-time helper; "
            "NOT part of the Snakemake DAG. Requires the scheme to be vendored "
            "beforehand (see workflows/bacmap/scripts/vendor_cgmlst_schemes.py)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--species",
        type=str,
        required=True,
        help=(
            "Species to build the reference for (case-insensitive, matched "
            "against the species column of samples.tsv). Initial supported "
            "scope: salmonella. DEC/Shigella/Vpara return a pending marker "
            "until their assemblies exist."
        ),
    )
    parser.add_argument(
        "--scheme",
        type=str,
        required=True,
        help=(
            "EnteroBase cgMLST scheme name (e.g. senterica_2, ecoli_2, "
            "vparahaemolyticus_3). Must already be vendored locally."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Directory to write reference_profiles.tsv + reference_meta.json. "
            "Defaults to data/reference/cgmlst/<species>/."
        ),
    )
    parser.add_argument(
        "--assemblies-dir",
        type=Path,
        default=DEFAULT_ASSEMBLIES_DIR,
        help=f"Root of assembled contigs (default: {DEFAULT_ASSEMBLIES_DIR})",
    )
    parser.add_argument(
        "--gmlst-bin",
        type=str,
        default=None,
        help=f"Path to gmlst binary (default: {DEFAULT_GMLST_BIN}, or PATH lookup)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=DEFAULT_THREADS,
        help=f"Threads per gmlst run (default: {DEFAULT_THREADS})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_S,
        help=f"Per-sample gmlst timeout in seconds (default: {DEFAULT_TIMEOUT_S})",
    )
    args = parser.parse_args(argv)

    output_dir = args.output_dir or (DEFAULT_REFERENCE_ROOT / args.species.lower())

    try:
        gmlst_bin = _resolve_gmlst_bin(args.gmlst_bin)
    except FileNotFoundError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    return build_reference(
        species=args.species,
        scheme=args.scheme,
        output_dir=output_dir,
        assemblies_dir=args.assemblies_dir,
        gmlst_bin=gmlst_bin,
        threads=args.threads,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
