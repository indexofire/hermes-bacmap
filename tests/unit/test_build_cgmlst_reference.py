"""Tests for ``scripts/build_cgmlst_reference.py``.

The build script shells out to the gmlst binary, which is slow and
network-dependent (scheme must be vendored first). These tests therefore
exercise the PURE-Python pieces directly:
  * ``merge_profiles``       — per-sample TSV merge + header-consistency guard
  * ``_write_meta``          — reference_meta.json shape + status flags
  * ``discover_reference_assemblies`` — samples.tsv × on-disk assembly dirs
  * ``build_reference``      — end-to-end with ``_run_one_sample`` stubbed

No real gmlst invocation happens anywhere in this file.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
_SRC_DIR = _PROJECT_ROOT / "src"

# scripts/ must precede src/ so the script's `from _common import ...` resolves
# against the scripts dir rather than any installed package of the same name.
for _p in (_SCRIPTS_DIR, _SRC_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Load the script as a module (it's not in a package).
_SPEC = importlib.util.spec_from_file_location(
    "build_cgmlst_reference", _SCRIPTS_DIR / "build_cgmlst_reference.py"
)
assert _SPEC is not None and _SPEC.loader is not None
build_cgmlst_reference = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_cgmlst_reference)


def _make_per_sample_tsv(path: Path, sample: str, scheme: str, alleles: list[str]) -> None:
    """Write a single-sample cgMLST TSV matching gmlst's output format."""
    loci = [f"L{i}" for i in range(1, len(alleles) + 1)]
    header = "\t".join(["File", "Scheme", "ST", *loci])
    row = "\t".join([sample, scheme, "-", *alleles])
    path.write_text(f"{header}\n{row}\n")


# ---------------------------------------------------------------------------
# merge_profiles
# ---------------------------------------------------------------------------


class TestMergeProfiles:
    def _three_samples(self, tmp_path: Path) -> list[tuple[str, Path]]:
        out = []
        for sid, alleles in [
            ("S1", ["1", "2", "3"]),
            ("S2", ["1", "5", "3"]),
            ("S3", ["7", "8", "9"]),
        ]:
            p = tmp_path / f"{sid}.tsv"
            _make_per_sample_tsv(p, sid, "synthetic", alleles)
            out.append((sid, p))
        return out

    def test_merges_into_multi_sample_tsv(self, tmp_path):
        per_sample = self._three_samples(tmp_path)
        out_tsv = tmp_path / "ref" / "reference_profiles.tsv"
        n_loci, merged, failures = build_cgmlst_reference.merge_profiles(
            per_sample, out_tsv
        )
        assert n_loci == 3
        assert merged == ["S1", "S2", "S3"]
        assert failures == []
        text = out_tsv.read_text()
        lines = text.strip().split("\n")
        assert lines[0] == "File\tScheme\tST\tL1\tL2\tL3"
        assert lines[1].startswith("S1\t")
        assert lines[2].startswith("S2\t")
        assert lines[3].startswith("S3\t")
        assert text.endswith("\n")

    def test_trailing_newline_present(self, tmp_path):
        per_sample = self._three_samples(tmp_path)
        out_tsv = tmp_path / "ref.tsv"
        build_cgmlst_reference.merge_profiles(per_sample, out_tsv)
        assert out_tsv.read_text().endswith("\n")

    def test_header_mismatch_recorded_as_failure(self, tmp_path):
        s1 = tmp_path / "S1.tsv"
        _make_per_sample_tsv(s1, "S1", "sch", ["1", "2"])
        # S2 has a DIFFERENT locus set — should be flagged as scheme drift.
        s2 = tmp_path / "S2.tsv"
        _make_per_sample_tsv(s2, "S2", "sch", ["1", "2", "3"])
        n_loci, merged, failures = build_cgmlst_reference.merge_profiles(
            [("S1", s1), ("S2", s2)], tmp_path / "out.tsv"
        )
        assert merged == ["S1"]
        assert len(failures) == 1
        assert failures[0][0] == "S2"
        assert "header mismatch" in failures[0][1]
        assert n_loci == 2  # locus count from the canonical (S1) header

    def test_missing_tsv_recorded_as_failure(self, tmp_path):
        s1 = tmp_path / "S1.tsv"
        _make_per_sample_tsv(s1, "S1", "sch", ["1"])
        per_sample = [("S1", s1), ("S2", tmp_path / "nonexistent.tsv")]
        _, merged, failures = build_cgmlst_reference.merge_profiles(
            per_sample, tmp_path / "out.tsv"
        )
        assert merged == ["S1"]
        assert failures == [("S2", "per-sample TSV missing")]

    def test_malformed_tsv_recorded_as_failure(self, tmp_path):
        s1 = tmp_path / "S1.tsv"
        _make_per_sample_tsv(s1, "S1", "sch", ["1", "2"])
        # Header-only file: no data row → _read_header_and_row raises.
        bad = tmp_path / "S2.tsv"
        bad.write_text("File\tScheme\tST\tL1\tL2\n")
        _, merged, failures = build_cgmlst_reference.merge_profiles(
            [("S1", s1), ("S2", bad)], tmp_path / "out.tsv"
        )
        assert merged == ["S1"]
        assert len(failures) == 1
        assert failures[0][0] == "S2"


# ---------------------------------------------------------------------------
# _write_meta
# ---------------------------------------------------------------------------


class TestWriteMeta:
    def test_built_status_no_failures(self, tmp_path):
        meta_path = tmp_path / "reference_meta.json"
        meta = build_cgmlst_reference._write_meta(
            meta_path,
            scheme="senterica_2",
            n_loci=3002,
            source_genomes=["SAM-TYP-001", "SAM-TYP-002"],
            gmlst_version="gmlst, version 0.1.1",
            status="built",
        )
        assert meta["scheme"] == "senterica_2"
        assert meta["n_loci"] == 3002
        assert meta["source_genomes"] == ["SAM-TYP-001", "SAM-TYP-002"]
        assert meta["status"] == "built"
        assert meta["gmlst_version"] == "gmlst, version 0.1.1"
        assert "built_at" in meta
        assert "failures" not in meta  # omitted when None
        # Round-trips through JSON.
        on_disk = json.loads(meta_path.read_text())
        assert on_disk["source_genomes"] == ["SAM-TYP-001", "SAM-TYP-002"]

    def test_partial_status_records_failures(self, tmp_path):
        meta = build_cgmlst_reference._write_meta(
            tmp_path / "reference_meta.json",
            scheme="ecoli_2",
            n_loci=2513,
            source_genomes=["S1"],
            gmlst_version="0.1.1",
            status="partial",
            failures=[("S2", "timeout after 3600s")],
        )
        assert meta["status"] == "partial"
        assert meta["failures"] == [{"sample": "S2", "reason": "timeout after 3600s"}]

    def test_pending_status_for_empty_library(self, tmp_path):
        meta = build_cgmlst_reference._write_meta(
            tmp_path / "reference_meta.json",
            scheme="vparahaemolyticus_3",
            n_loci=0,
            source_genomes=[],
            gmlst_version="0.1.1",
            status="pending_assemblies",
        )
        assert meta["status"] == "pending_assemblies"
        assert meta["source_genomes"] == []
        assert meta["n_loci"] == 0

    def test_built_at_is_iso_utc(self, tmp_path):
        import datetime as dt

        meta = build_cgmlst_reference._write_meta(
            tmp_path / "reference_meta.json",
            scheme="x",
            n_loci=1,
            source_genomes=[],
            gmlst_version="x",
            status="built",
        )
        # Must parse as an ISO-8601 timestamp with tz info.
        parsed = dt.datetime.fromisoformat(meta["built_at"])
        assert parsed.tzinfo is not None


# ---------------------------------------------------------------------------
# discover_reference_assemblies
# ---------------------------------------------------------------------------


class TestDiscoverReferenceAssemblies:
    def test_finds_salmonella_assemblies(self, tmp_path):
        # Mirror the real data/assemblies layout with 3 stub Salmonella dirs.
        for sid in ("SAM-TYP-001", "SAM-TYP-002", "SAM-ENT-003"):
            d = tmp_path / sid
            d.mkdir()
            (d / "contigs.fasta").write_text(">contig1\nACGT\n")

        # Build a minimal samples.tsv the helper will read.
        samples_tsv = tmp_path / "samples.tsv"
        samples_tsv.write_text(
            "sample\tspecies\tR1\tR2\n"
            "SAM-TYP-001\tSalmonella\tr1\tr2\n"
            "SAM-TYP-002\tSalmonella\tr1\tr2\n"
            "SAM-ENT-003\tSalmonella\tr1\tr2\n"
            "SAM-DEC-012\tE.coli\tr1\tr2\n"
        )

        # Patch SAMPLES_TSV so the helper reads our fixture.
        orig = build_cgmlst_reference.SAMPLES_TSV
        build_cgmlst_reference.SAMPLES_TSV = samples_tsv
        try:
            pairs = build_cgmlst_reference.discover_reference_assemblies(
                "salmonella", tmp_path
            )
        finally:
            build_cgmlst_reference.SAMPLES_TSV = orig

        ids = [sid for sid, _ in pairs]
        assert ids == ["SAM-ENT-003", "SAM-TYP-001", "SAM-TYP-002"]  # sorted

    def test_species_match_is_case_insensitive(self, tmp_path):
        d = tmp_path / "SAM-X"
        d.mkdir()
        (d / "contigs.fasta").write_text("x")
        samples_tsv = tmp_path / "samples.tsv"
        samples_tsv.write_text("sample\tspecies\tR1\tR2\nSAM-X\tSalmonella\ta\tb\n")

        orig = build_cgmlst_reference.SAMPLES_TSV
        build_cgmlst_reference.SAMPLES_TSV = samples_tsv
        try:
            # Lowercase query must still match the mixed-case species column.
            assert len(
                build_cgmlst_reference.discover_reference_assemblies(
                    "SALMONELLA", tmp_path
                )
            ) == 1
            assert len(
                build_cgmlst_reference.discover_reference_assemblies(
                    "salmonella", tmp_path
                )
            ) == 1
        finally:
            build_cgmlst_reference.SAMPLES_TSV = orig

    def test_missing_assembly_dir_skipped(self, tmp_path):
        # samples.tsv lists a Salmonella sample, but no assembly dir on disk.
        samples_tsv = tmp_path / "samples.tsv"
        samples_tsv.write_text(
            "sample\tspecies\tR1\tR2\nSAM-GHOST\tSalmonella\ta\tb\n"
        )
        orig = build_cgmlst_reference.SAMPLES_TSV
        build_cgmlst_reference.SAMPLES_TSV = samples_tsv
        try:
            assert (
                build_cgmlst_reference.discover_reference_assemblies(
                    "salmonella", tmp_path
                )
                == []
            )
        finally:
            build_cgmlst_reference.SAMPLES_TSV = orig

    def test_other_species_excluded(self, tmp_path):
        d = tmp_path / "SAM-DEC"
        d.mkdir()
        (d / "contigs.fasta").write_text("x")
        samples_tsv = tmp_path / "samples.tsv"
        samples_tsv.write_text(
            "sample\tspecies\tR1\tR2\nSAM-DEC\tE.coli\ta\tb\n"
        )
        orig = build_cgmlst_reference.SAMPLES_TSV
        build_cgmlst_reference.SAMPLES_TSV = samples_tsv
        try:
            # Querying salmonella must NOT pick up the E.coli sample.
            assert (
                build_cgmlst_reference.discover_reference_assemblies(
                    "salmonella", tmp_path
                )
                == []
            )
        finally:
            build_cgmlst_reference.SAMPLES_TSV = orig


# ---------------------------------------------------------------------------
# build_reference — end-to-end with _run_one_sample stubbed (no real gmlst)
# ---------------------------------------------------------------------------


class TestBuildReferenceStubbed:
    """Monkeypatches ``_run_one_sample`` so no real gmlst binary is invoked."""

    def _make_assemblies(self, tmp_path: Path, samples: list[str]) -> Path:
        assemblies = tmp_path / "assemblies"
        assemblies.mkdir()
        rows = ["sample\tspecies\tR1\tR2"]
        for sid in samples:
            d = assemblies / sid
            d.mkdir()
            (d / "contigs.fasta").write_text(">c\nACGT\n")
            rows.append(f"{sid}\tSalmonella\tr1\tr2")
        (tmp_path / "samples.tsv").write_text("\n".join(rows) + "\n")
        return assemblies

    def test_build_success(self, tmp_path, monkeypatch):
        assemblies = self._make_assemblies(tmp_path, ["SAM-A", "SAM-B"])
        output_dir = tmp_path / "ref"

        def fake_run(gmlst_bin, scheme, sample_id, contigs, out_tsv, threads, timeout):
            _make_per_sample_tsv(out_tsv, sample_id, scheme, ["1", "2", "3"])
            return (True, "")

        monkeypatch.setattr(
            build_cgmlst_reference, "_run_one_sample", fake_run
        )
        monkeypatch.setattr(
            build_cgmlst_reference,
            "_gmlst_version",
            lambda bin: "gmlst, version 0.1.1",
        )

        # Point SAMPLES_TSV at our fixture so discovery reads it.
        monkeypatch.setattr(
            build_cgmlst_reference, "SAMPLES_TSV", tmp_path / "samples.tsv"
        )

        rc = build_cgmlst_reference.build_reference(
            species="salmonella",
            scheme="senterica_2",
            output_dir=output_dir,
            assemblies_dir=assemblies,
            gmlst_bin="/fake/gmlst",
            threads=1,
            timeout=10,
        )
        assert rc == 0

        profiles_tsv = output_dir / "reference_profiles.tsv"
        meta_path = output_dir / "reference_meta.json"
        assert profiles_tsv.exists()
        assert meta_path.exists()

        # Merged TSV: one header + two data rows.
        lines = profiles_tsv.read_text().strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "File\tScheme\tST\tL1\tL2\tL3"

        meta = json.loads(meta_path.read_text())
        assert meta["scheme"] == "senterica_2"
        assert meta["n_loci"] == 3
        assert meta["source_genomes"] == ["SAM-A", "SAM-B"]
        assert meta["status"] == "built"
        assert meta["gmlst_version"] == "gmlst, version 0.1.1"
        assert "failures" not in meta

    def test_build_partial_when_one_sample_fails(self, tmp_path, monkeypatch):
        assemblies = self._make_assemblies(tmp_path, ["SAM-A", "SAM-B"])
        output_dir = tmp_path / "ref"

        def fake_run(gmlst_bin, scheme, sample_id, contigs, out_tsv, threads, timeout):
            if sample_id == "SAM-B":
                return (False, "simulated gmlst failure")
            _make_per_sample_tsv(out_tsv, sample_id, scheme, ["1", "2"])
            return (True, "")

        monkeypatch.setattr(build_cgmlst_reference, "_run_one_sample", fake_run)
        monkeypatch.setattr(
            build_cgmlst_reference, "_gmlst_version", lambda bin: "0.1.1"
        )
        monkeypatch.setattr(
            build_cgmlst_reference, "SAMPLES_TSV", tmp_path / "samples.tsv"
        )

        rc = build_cgmlst_reference.build_reference(
            species="salmonella",
            scheme="senterica_2",
            output_dir=output_dir,
            assemblies_dir=assemblies,
            gmlst_bin="/fake/gmlst",
            threads=1,
            timeout=10,
        )
        # Partial → exit non-zero so CI/operators notice.
        assert rc == 1

        meta = json.loads((output_dir / "reference_meta.json").read_text())
        assert meta["status"] == "partial"
        assert meta["source_genomes"] == ["SAM-A"]
        assert meta["failures"] == [
            {"sample": "SAM-B", "reason": "simulated gmlst failure"}
        ]
        # The one successful profile is still written.
        lines = (output_dir / "reference_profiles.tsv").read_text().strip().split("\n")
        assert len(lines) == 2  # header + SAM-A

    def test_build_pending_when_no_assemblies(self, tmp_path, monkeypatch):
        # samples.tsv lists a Salmonella sample, but no assembly dir exists.
        (tmp_path / "samples.tsv").write_text(
            "sample\tspecies\tR1\tR2\nSAM-GHOST\tSalmonella\ta\tb\n"
        )
        monkeypatch.setattr(
            build_cgmlst_reference, "SAMPLES_TSV", tmp_path / "samples.tsv"
        )
        monkeypatch.setattr(
            build_cgmlst_reference, "_gmlst_version", lambda bin: "0.1.1"
        )
        output_dir = tmp_path / "ref"

        rc = build_cgmlst_reference.build_reference(
            species="salmonella",
            scheme="senterica_2",
            output_dir=output_dir,
            assemblies_dir=tmp_path / "assemblies",  # empty / nonexistent
            gmlst_bin="/fake/gmlst",
            threads=1,
            timeout=10,
        )
        assert rc == 1
        meta = json.loads((output_dir / "reference_meta.json").read_text())
        assert meta["status"] == "pending_assemblies"
        assert meta["source_genomes"] == []
        assert not (output_dir / "reference_profiles.tsv").exists()

    def test_build_gmlst_all_failed(self, tmp_path, monkeypatch):
        assemblies = self._make_assemblies(tmp_path, ["SAM-A"])
        monkeypatch.setattr(
            build_cgmlst_reference,
            "_run_one_sample",
            lambda *a, **kw: (False, "boom"),
        )
        monkeypatch.setattr(
            build_cgmlst_reference, "_gmlst_version", lambda bin: "0.1.1"
        )
        monkeypatch.setattr(
            build_cgmlst_reference, "SAMPLES_TSV", tmp_path / "samples.tsv"
        )

        rc = build_cgmlst_reference.build_reference(
            species="salmonella",
            scheme="senterica_2",
            output_dir=tmp_path / "ref",
            assemblies_dir=assemblies,
            gmlst_bin="/fake/gmlst",
            threads=1,
            timeout=10,
        )
        assert rc == 1
        meta = json.loads((tmp_path / "ref" / "reference_meta.json").read_text())
        assert meta["status"] == "gmlst_failed"
        assert meta["source_genomes"] == []


# ---------------------------------------------------------------------------
# argparse contract
# ---------------------------------------------------------------------------


class TestArgparseContract:
    def test_required_args_present(self):
        assert callable(build_cgmlst_reference.main)
        assert callable(build_cgmlst_reference.build_reference)

    def test_missing_species_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc:
            build_cgmlst_reference.main(["--scheme", "senterica_2"])
        assert exc.value.code == 2
        assert "species" in capsys.readouterr().err.lower()

    def test_missing_scheme_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc:
            build_cgmlst_reference.main(["--species", "salmonella"])
        assert exc.value.code == 2
        assert "scheme" in capsys.readouterr().err.lower()

    def test_output_dir_defaults_to_species_subdir(self, tmp_path, monkeypatch):
        """When --output-dir is omitted it defaults to
        data/reference/cgmlst/<species>/ — verified by intercepting
        build_reference."""
        captured: dict = {}

        def fake_build(**kwargs):
            captured.update(kwargs)
            return 0

        monkeypatch.setattr(build_cgmlst_reference, "build_reference", fake_build)
        monkeypatch.setattr(
            build_cgmlst_reference,
            "_resolve_gmlst_bin",
            lambda explicit: "/fake/gmlst",
        )

        rc = build_cgmlst_reference.main(
            ["--species", "salmonella", "--scheme", "senterica_2"]
        )
        assert rc == 0
        expected = (
            build_cgmlst_reference.DEFAULT_REFERENCE_ROOT / "salmonella"
        )
        assert captured["output_dir"] == expected
        assert captured["species"] == "salmonella"
        assert captured["scheme"] == "senterica_2"

    def test_explicit_output_dir_respected(self, tmp_path, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(
            build_cgmlst_reference,
            "build_reference",
            lambda **kw: captured.update(kw) or 0,
        )
        monkeypatch.setattr(
            build_cgmlst_reference,
            "_resolve_gmlst_bin",
            lambda explicit: "/fake/gmlst",
        )
        custom = tmp_path / "custom"
        build_cgmlst_reference.main(
            [
                "--species",
                "salmonella",
                "--scheme",
                "senterica_2",
                "--output-dir",
                str(custom),
            ]
        )
        assert captured["output_dir"] == custom
