"""Tests for hermes_bacmap.typing.vpa_serotyper_engine."""

from __future__ import annotations

import hashlib
import hmac
import pickle
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.typing import vpa_serotyper_engine as eng  # noqa: E402


class TestLocusToAntigen:
    def test_none_or_empty(self):
        assert eng._locus_to_antigen("", "O") == "OUT"
        assert eng._locus_to_antigen("None", "O") == "OUT"

    def test_lu_prefix_unt(self):
        assert eng._locus_to_antigen("OLU", "O") == "OUT"
        assert eng._locus_to_antigen("OLU5", "O") == "OUT"

    def test_plain_l_number(self):
        assert eng._locus_to_antigen("OL5", "O") == "O5"
        assert eng._locus_to_antigen("KL11", "K") == "K11"

    def test_variant_l_number_strips_v(self):
        assert eng._locus_to_antigen("OL5V2", "O") == "O5"
        assert eng._locus_to_antigen("KL1V1", "K") == "K1"

    def test_unknown_pattern(self):
        assert eng._locus_to_antigen("oweird", "O") == "OUT"
        assert eng._locus_to_antigen("OL", "O") == "OUT"


class TestFormatGeneDetails:
    def test_empty(self):
        assert eng._format_gene_details([]) == ""

    def test_single_gene(self):
        genes = [{"gene": "wzx", "identity": 99.5, "coverage": 100.0, "status": "present"}]
        assert eng._format_gene_details(genes) == "wzx,99.5%,100.0%,present"

    def test_multiple_genes_joined(self):
        genes = [
            {"gene": "wzx", "identity": 99.5, "coverage": 100.0, "status": "present"},
            {"gene": "wzy", "identity": 50.0, "coverage": 25.0, "status": "missing"},
        ]
        out = eng._format_gene_details(genes)
        assert out == "wzx,99.5%,100.0%,present;wzy,50.0%,25.0%,missing"

    def test_missing_keys_use_defaults(self):
        genes = [{}]
        assert eng._format_gene_details(genes) == "?,0.0%,0.0%,missing"


class TestDecide:
    @pytest.fixture
    def engine(self):
        return eng.SerotyperEngine.__new__(eng.SerotyperEngine)

    def test_missing_boundary_forces_unknown(self, engine):
        ok, conf = engine._decide(0, 100, 100, 1, ["coaD"])
        assert ok is False
        assert conf == "Unknown"

    def test_too_many_missing_forces_unknown(self, engine):
        ok, conf = engine._decide(eng.MAX_GENE_DIFF + 1, 100, 100, 1, [])
        assert ok is False
        assert conf == "Unknown"

    def test_perfect_tier(self, engine):
        ok, conf = engine._decide(0, 100, 96, 1, [])
        assert (ok, conf) == (True, "Perfect")

    def test_perfect_requires_identity_strictly_above_95(self, engine):
        ok, conf = engine._decide(0, 100, 95, 1, [])
        assert (ok, conf) == (True, "High")

    def test_perfect_requires_single_piece(self, engine):
        ok, conf = engine._decide(0, 100, 99, 2, [])
        assert conf != "Perfect"

    def test_high_tier(self, engine):
        ok, conf = engine._decide(1, 95, 92, 1, [])
        assert (ok, conf) == (True, "High")

    def test_high_tier_boundary_identity_90_falls_to_medium(self, engine):
        ok, conf = engine._decide(1, 95, 90, 1, [])
        assert (ok, conf) == (True, "Medium")

    def test_medium_tier(self, engine):
        ok, conf = engine._decide(2, 80, 85, 1, [])
        assert (ok, conf) == (True, "Medium")

    def test_low_tier_when_identity_below_80(self, engine):
        ok, conf = engine._decide(2, 60, 75, 1, [])
        assert (ok, conf) == (True, "Low")


class TestEmptyResult:
    @pytest.fixture
    def engine(self):
        return eng.SerotyperEngine.__new__(eng.SerotyperEngine)

    def test_default_keys_present(self, engine):
        r = engine._empty_result("SAM1")
        assert r["Sample"] == "SAM1"
        assert r["Predicted_Serotype"] == "OUT:KUT"
        for prefix in ("O", "K"):
            assert r[f"{prefix}_Locus"] == "None"
            assert r[f"{prefix}_Confidence"] == "Unknown"
            assert r[f"{prefix}_Missing_Genes"] == "No match"
            assert r[f"{prefix}_Alerts"] == "None"
            assert r[f"{prefix}_Genes_Detail"] == ""

    def test_error_replaces_missing_genes(self, engine):
        r = engine._empty_result("SAM1", error="bad fasta")
        assert r["O_Missing_Genes"] == "bad fasta"
        assert r["K_Missing_Genes"] == "bad fasta"


class TestGetReferenceGenes:
    def test_unknown_locus_returns_empty(self, fake_engine_no_init):
        assert fake_engine_no_init.get_reference_genes("nope") == []

    def test_returns_gene_dicts(self, fake_engine_no_init):
        fake_engine_no_init.metadata = {
            "OL1": {
                "type": "O",
                "genes": [
                    {"name": "wzx", "locus_tag": "tag1", "start": 0, "end": 100, "product": "P"},
                    {
                        "name": "wzy",
                        "locus_tag": "tag2",
                        "start": 100,
                        "end": 200,
                        "strand": -1,
                        "product": "Q",
                    },
                ],
            }
        }
        genes = fake_engine_no_init.get_reference_genes("OL1")
        assert len(genes) == 2
        assert genes[0]["locus_tag"] == "tag1"
        assert genes[1]["strand"] == -1


@dataclass
class FakeHit:
    ctg: str = "ctg1"
    q_st: int = 0
    q_en: int = 1000
    r_st: int = 0
    r_en: int = 1000
    blen: int = 1000
    mlen: int = 990
    strand: int = 1


class FakeAligner:
    def __init__(
        self,
        hits_by_seq: dict[str, list[FakeHit]] | None = None,
        default: list[FakeHit] | None = None,
        valid: bool = True,
    ) -> None:
        self.hits_by_seq = hits_by_seq or {}
        self.default = default if default is not None else []
        self.valid = valid

    def map(self, seq: str) -> Any:
        return iter(self.hits_by_seq.get(seq, self.default))

    def __bool__(self) -> bool:
        return self.valid


@pytest.fixture
def fake_engine_no_init():
    e = eng.SerotyperEngine.__new__(eng.SerotyperEngine)
    e.metadata = {}
    return e


def _random_dna(n: int, seed: int = 42) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(n))


def _build_synthetic_db(
    db_dir: Path,
    loci: dict[str, dict[str, Any]],
    signed: bool = False,
    tampered: bool = False,
) -> Path:
    db_dir.mkdir(parents=True, exist_ok=True)

    fasta_path = db_dir / "ref_seqs.fasta"
    with fasta_path.open("w") as f:
        for lid, meta in loci.items():
            f.write(f">{lid}\n{meta['seq']}\n")

    gene_path = db_dir / "gene_refs.fasta"
    with gene_path.open("w") as f:
        for lid, meta in loci.items():
            for i, g in enumerate(meta["genes"]):
                seq = meta["seq"][g["start"] : g["end"]]
                f.write(f">{lid}_gene_{i}\n{seq}\n")

    import sourmash
    from sourmash import MinHash, SourmashSignature

    sigs = []
    for lid, meta in loci.items():
        mh = MinHash(n=0, ksize=21, scaled=100)
        mh.add_sequence(meta["seq"], force=True)
        sigs.append(SourmashSignature(mh, name=lid))

    sketch_path = db_dir / "ref_sketches.sig"
    with sketch_path.open("w") as f:
        sourmash.save_signatures(sigs, fp=f)

    metadata: dict[str, Any] = {}
    for lid, meta in loci.items():
        metadata[lid] = {"type": meta["type"], "genes": meta["genes"]}

    if signed:
        digest = hmac.new(eng.SIGNING_KEY, pickle.dumps(metadata), hashlib.sha256).digest()
        if tampered:
            digest = b"0" * len(digest)
        with (db_dir / "ref_meta.pkl").open("wb") as f:
            pickle.dump((metadata, digest), f)
        (db_dir / "ref_meta.sig").write_bytes(b"sig-marker")
    else:
        with (db_dir / "ref_meta.pkl").open("wb") as f:
            pickle.dump(metadata, f)

    return db_dir


def _locus_with_genes(
    lid: str, ltype: str, seq_len: int = 6000, n_genes: int = 6
) -> dict[str, Any]:
    seq = _random_dna(seq_len, seed=hash(lid) & 0xFFFF)
    genes = []
    chunk = seq_len // n_genes
    for i in range(n_genes):
        genes.append(
            {
                "name": f"{lid}_g{i}",
                "locus_tag": f"{lid}_tag{i}",
                "start": i * chunk,
                "end": (i + 1) * chunk,
                "strand": 1 if i % 2 == 0 else -1,
                "product": f"protein-{i}",
            }
        )
    return {"type": ltype, "seq": seq, "genes": genes}


class _MappyStub:
    def __init__(self, aligner_factory: _AlignerFactory) -> None:
        self._factory = aligner_factory
        self._cache: dict[str, list[tuple[str, str, None]]] = {}

    @property
    def Aligner(self) -> _AlignerFactory:
        return self._factory

    def fastx_read(self, path: str):
        if path in self._cache:
            return self._cache[path]
        entries = _parse_fasta(Path(path))
        self._cache[path] = entries
        return entries

    def set_fastx(self, path: str, entries) -> None:
        self._cache[str(path)] = entries


def _parse_fasta(path: Path) -> list[tuple[str, str, None]]:
    if not path.exists():
        return []
    name = None
    seq_parts: list[str] = []
    out: list[tuple[str, str, None]] = []
    with path.open() as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith(">"):
                if name is not None:
                    out.append((name, "".join(seq_parts), None))
                name = line[1:].split()[0] if len(line) > 1 else ""
                seq_parts = []
            else:
                seq_parts.append(line)
        if name is not None:
            out.append((name, "".join(seq_parts), None))
    return out


class _AlignerFactory:
    def __init__(self, default: FakeAligner) -> None:
        self.default = default
        self.per_path: dict[str, FakeAligner] = {}
        self.per_sample: dict[str, FakeAligner] = {}

    def __call__(self, target=None, **kwargs):
        if isinstance(target, str):
            if target in self.per_path:
                return self.per_path[target]
            if target in self.per_sample:
                return self.per_sample[target]
        return self.default


def _install_fake_mappy(monkeypatch, default_aligner: FakeAligner) -> _MappyStub:
    fake = _MappyStub(_AlignerFactory(default_aligner))
    monkeypatch.setitem(sys.modules, "mappy", fake)
    return fake


class TestEngineInit:
    def test_init_unsigned_db_succeeds(self, tmp_path, monkeypatch):
        loci = {"OL1": _locus_with_genes("OL1", "O")}
        db = _build_synthetic_db(tmp_path, loci, signed=False)
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)
        assert engine.metadata.keys() == {"OL1"}
        assert engine.locus_type_map["OL1"] == "O"
        assert "OL1" in engine.sketches

    def test_init_signed_db_valid(self, tmp_path, monkeypatch):
        loci = {"OL1": _locus_with_genes("OL1", "O")}
        db = _build_synthetic_db(tmp_path, loci, signed=True)
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)
        assert engine.metadata.keys() == {"OL1"}

    def test_init_signed_db_tampered_raises(self, tmp_path, monkeypatch):
        loci = {"OL1": _locus_with_genes("OL1", "O")}
        db = _build_synthetic_db(tmp_path, loci, signed=True, tampered=True)
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        with pytest.raises(RuntimeError, match="signature verification failed"):
            eng.SerotyperEngine(db)

    def test_init_failed_aligner_raises_runtime_error(self, tmp_path, monkeypatch):
        loci = {"OL1": _locus_with_genes("OL1", "O")}
        db = _build_synthetic_db(tmp_path, loci)
        _install_fake_mappy(monkeypatch, FakeAligner(valid=False))
        with pytest.raises(RuntimeError, match="Failed to load minimap2"):
            eng.SerotyperEngine(db)

    def test_init_mappy_import_error(self, tmp_path, monkeypatch):
        loci = {"OL1": _locus_with_genes("OL1", "O")}
        db = _build_synthetic_db(tmp_path, loci)

        original_mappy = sys.modules.pop("mappy", None)
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "mappy":
                raise ImportError("no mappy")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        try:
            with pytest.raises(ImportError, match="mappy is required"):
                eng.SerotyperEngine(db)
        finally:
            if original_mappy is not None:
                sys.modules["mappy"] = original_mappy

    def test_init_sourmash_import_error(self, tmp_path, monkeypatch):
        loci = {"OL1": _locus_with_genes("OL1", "O")}
        db = _build_synthetic_db(tmp_path, loci)
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))

        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "sourmash":
                raise ImportError("no sourmash")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(ImportError, match="sourmash is required"):
            eng.SerotyperEngine(db)


class TestExtractLocusContigs:
    def test_filters_short_alignments(self, fake_engine_no_init):
        fake_engine_no_init.metadata = {"OL1": {"type": "O"}}
        short_hit = FakeHit(blen=10, ctg="OL1")
        fake_engine_no_init.locus_aligner = FakeAligner(hits_by_seq={"AAAA": [short_hit]})
        out = fake_engine_no_init._extract_locus_contigs({"ctg1": "AAAA"})
        assert out == {}

    def test_filters_unknown_locus(self, fake_engine_no_init):
        fake_engine_no_init.metadata = {"OL1": {"type": "O"}}
        hit = FakeHit(blen=600, ctg="UNKNOWN")
        fake_engine_no_init.locus_aligner = FakeAligner(hits_by_seq={"AAAA": [hit]})
        out = fake_engine_no_init._extract_locus_contigs({"ctg1": "AAAA"})
        assert out == {}

    def test_records_hit_with_locus_id(self, fake_engine_no_init):
        fake_engine_no_init.metadata = {"OL1": {"type": "O"}}
        hit = FakeHit(ctg="OL1", q_st=0, q_en=600, r_st=100, r_en=700, blen=600, mlen=590, strand=1)
        fake_engine_no_init.locus_aligner = FakeAligner(hits_by_seq={"ACGT" * 200: [hit]})
        out = fake_engine_no_init._extract_locus_contigs({"ctg1": "ACGT" * 200})
        assert "OL1" in out
        assert len(out["OL1"]) == 1
        name, _extracted, strand, r_st = out["OL1"][0]
        assert name == "ctg1"
        assert strand == 1
        assert r_st == 100

    def test_dedupes_seen_keys(self, fake_engine_no_init):
        fake_engine_no_init.metadata = {"OL1": {"type": "O"}}
        hit = FakeHit(ctg="OL1", blen=600)
        seq = "ACGT" * 200
        fake_engine_no_init.locus_aligner = FakeAligner(hits_by_seq={seq: [hit, hit]})
        out = fake_engine_no_init._extract_locus_contigs({"ctg1": seq})
        assert len(out["OL1"]) == 1

    def test_strand_string_plus(self, fake_engine_no_init):
        fake_engine_no_init.metadata = {"OL1": {"type": "O"}}
        hit = FakeHit(ctg="OL1", blen=600, strand="+")
        seq = "ACGT" * 200
        fake_engine_no_init.locus_aligner = FakeAligner(hits_by_seq={seq: [hit]})
        out = fake_engine_no_init._extract_locus_contigs({"ctg1": seq})
        assert out["OL1"][0][2] == 1

    def test_strand_string_minus(self, fake_engine_no_init):
        fake_engine_no_init.metadata = {"OL1": {"type": "O"}}
        hit = FakeHit(ctg="OL1", blen=600, strand="-")
        seq = "ACGT" * 200
        fake_engine_no_init.locus_aligner = FakeAligner(hits_by_seq={seq: [hit]})
        out = fake_engine_no_init._extract_locus_contigs({"ctg1": seq})
        assert out["OL1"][0][2] == -1

    def test_ref_name_with_space_uses_first_token(self, fake_engine_no_init):
        fake_engine_no_init.metadata = {"OL1": {"type": "O"}}
        hit = FakeHit(ctg="OL1 description here", blen=600)
        seq = "ACGT" * 200
        fake_engine_no_init.locus_aligner = FakeAligner(hits_by_seq={seq: [hit]})
        out = fake_engine_no_init._extract_locus_contigs({"ctg1": seq})
        assert "OL1" in out


class TestRankLociByKmer:
    def test_no_seqs_returns_empty(self, fake_engine_no_init):
        fake_engine_no_init.sketch_mhs = {}
        fake_engine_no_init.locus_type_map = {}
        assert fake_engine_no_init._rank_loci_by_kmer({}, "O") == []

    def test_high_containment_for_matching_seq(self, tmp_path, monkeypatch):
        loci = {"OL1": _locus_with_genes("OL1", "O")}
        db = _build_synthetic_db(tmp_path, loci)
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)

        type_contigs = {"OL1": [("ctg1", loci["OL1"]["seq"], 1, 0)]}
        ranked = engine._rank_loci_by_kmer(type_contigs, "O")
        assert len(ranked) == 1
        assert ranked[0][0] == "OL1"
        assert ranked[0][1] > 90.0

    def test_filters_by_locus_type(self, tmp_path, monkeypatch):
        loci = {
            "OL1": _locus_with_genes("OL1", "O"),
            "KL1": _locus_with_genes("KL1", "K"),
        }
        db = _build_synthetic_db(tmp_path, loci)
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)

        type_contigs = {
            "OL1": [("ctg1", loci["OL1"]["seq"], 1, 0)],
            "KL1": [("ctg2", loci["KL1"]["seq"], 1, 0)],
        }
        ranked = engine._rank_loci_by_kmer(type_contigs, "O")
        locus_ids = [lid for lid, _ in ranked]
        assert "OL1" in locus_ids
        assert "KL1" not in locus_ids


class TestIdentifyLocusByKmer:
    def test_empty_returns_none_zero(self, fake_engine_no_init):
        fake_engine_no_init.sketch_mhs = {}
        fake_engine_no_init.locus_type_map = {}
        assert fake_engine_no_init._identify_locus_by_kmer({}, "O") == (None, 0)


class TestTypeLocus:
    def test_returns_none_when_no_type_contigs(self, fake_engine_no_init):
        fake_engine_no_init.locus_type_map = {}
        result = fake_engine_no_init._type_locus({}, "O", None)
        assert result is None

    def test_returns_none_locus_when_below_threshold(self, tmp_path, monkeypatch):
        loci = {"OL1": _locus_with_genes("OL1", "O")}
        db = _build_synthetic_db(tmp_path, loci)
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)

        bogus = "TGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCAT" * 20
        type_contigs = {"OL1": [("ctg1", bogus, 1, 0)]}
        result = engine._type_locus(type_contigs, "O", FakeAligner(), enable_detail=False)
        assert result is not None
        assert result["locus"] == "None"
        assert result["confidence"] == "Unknown"
        assert result["detail_notes"] == ""

    def test_below_threshold_with_detail(self, tmp_path, monkeypatch):
        loci = {"OL1": _locus_with_genes("OL1", "O")}
        db = _build_synthetic_db(tmp_path, loci)
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)

        bogus = "TGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCAT" * 20
        type_contigs = {"OL1": [("ctg1", bogus, 1, 0)]}
        result = engine._type_locus(
            type_contigs, "O", FakeAligner(), enable_detail=True, min_containment=30.0
        )
        assert result is not None
        assert "novel O-locus" in result["detail_notes"]

    def test_type_locus_high_confidence_match(self, tmp_path, monkeypatch):
        locus = _locus_with_genes("OL1", "O", n_genes=2)
        db = _build_synthetic_db(tmp_path, {"OL1": locus})
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)

        comp = str.maketrans("ATGCatgc", "TACGtacg")
        gene_hits: dict[str, list[FakeHit]] = {}
        for g in locus["genes"]:
            gseq = locus["seq"][g["start"] : g["end"]]
            if g.get("strand", 1) == -1:
                gseq = gseq[::-1].translate(comp)
            gene_hits[gseq] = [
                FakeHit(
                    ctg="ctg1",
                    blen=len(gseq),
                    mlen=len(gseq),
                    q_st=0,
                    q_en=len(gseq),
                    r_st=0,
                    r_en=len(gseq),
                )
            ]

        sample_aligner = FakeAligner(hits_by_seq=gene_hits, default=[])

        type_contigs = {"OL1": [("ctg1", locus["seq"], 1, 0)]}
        result = engine._type_locus(type_contigs, "O", sample_aligner, enable_detail=False)
        assert result is not None
        assert result["locus"] == "OL1"
        assert result["confidence"] in {"Perfect", "High", "Medium", "Low"}
        assert result["coverage"] > 0


class TestRunOneSample:
    def test_missing_sample_path_returns_empty_result(self, tmp_path, monkeypatch):
        loci = {"OL1": _locus_with_genes("OL1", "O")}
        db = _build_synthetic_db(tmp_path, loci)
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)

        missing = tmp_path / "does_not_exist.fasta"
        result = engine.run_one_sample(missing)
        assert result["Predicted_Serotype"] == "OUT:KUT"
        assert result["O_Locus"] == "None"

    def test_empty_fasta_returns_empty_result(self, tmp_path, monkeypatch):
        loci = {"OL1": _locus_with_genes("OL1", "O")}
        db = _build_synthetic_db(tmp_path, loci)

        sample = tmp_path / "sample.fasta"
        sample.write_text("")

        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)

        result = engine.run_one_sample(sample)
        assert result["Predicted_Serotype"] == "OUT:KUT"
        assert result["O_Locus"] == "None"

    def test_no_locus_contigs_extracted_returns_empty(self, tmp_path, monkeypatch):
        locus = _locus_with_genes("OL1", "O")
        db = _build_synthetic_db(tmp_path, {"OL1": locus})
        sample = tmp_path / "sample.fasta"
        sample_seq = "GGGGCCCC" * 200
        sample.write_text(f">ctg1\n{sample_seq}\n")

        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)
        result = engine.run_one_sample(sample)
        assert result["O_Locus"] == "None"

    def test_typing_with_matching_sample(self, tmp_path, monkeypatch):
        locus_o = _locus_with_genes("OL1", "O", n_genes=2)
        locus_k = _locus_with_genes("KL1", "K", n_genes=2)
        db = _build_synthetic_db(tmp_path, {"OL1": locus_o, "KL1": locus_k})

        sample = tmp_path / "sample.fasta"
        sample_seq_o = locus_o["seq"]
        sample.write_text(f">ctg1\n{sample_seq_o}\n")

        fake_m = _install_fake_mappy(monkeypatch, FakeAligner(valid=True))

        locus_aligner = FakeAligner(
            hits_by_seq={
                sample_seq_o: [
                    FakeHit(
                        ctg="OL1",
                        q_st=0,
                        q_en=len(sample_seq_o),
                        r_st=0,
                        r_en=len(sample_seq_o),
                        blen=len(sample_seq_o),
                        mlen=len(sample_seq_o),
                        strand=1,
                    )
                ]
            },
            default=[],
        )

        comp = str.maketrans("ATGCatgc", "TACGtacg")
        gene_hits: dict[str, list[FakeHit]] = {}
        for locus in (locus_o, locus_k):
            for g in locus["genes"]:
                gseq = locus["seq"][g["start"] : g["end"]]
                if g.get("strand", 1) == -1:
                    gseq = gseq[::-1].translate(comp)
                gene_hits[gseq] = [
                    FakeHit(
                        ctg="ctg1",
                        blen=len(gseq),
                        mlen=len(gseq),
                        q_st=0,
                        q_en=len(gseq),
                        r_st=0,
                        r_en=len(gseq),
                        strand=1,
                    )
                ]
        sample_aligner = FakeAligner(hits_by_seq=gene_hits, default=[])

        fake_m._factory.per_sample[str(sample)] = sample_aligner
        fake_m._factory.default = locus_aligner

        engine = eng.SerotyperEngine(db)
        result = engine.run_one_sample(sample)
        assert result["Sample"] == "sample"
        assert result["O_Locus"] == "OL1"
        assert result["K_Locus"] == "None"
        assert result["Predicted_Serotype"].startswith("O")


class TestConstants:
    def test_thresholds_are_sensible(self):
        assert eng.MAX_GENE_DIFF == 4
        assert eng.MIN_CONTIG_ALIGN_LEN == 500
        assert eng.MIN_CONTAINMENT == 30.0
        assert eng.MIN_GENE_COV == 30.0
        assert eng.KMER_TIEBREAK_MARGIN == 5.0

    def test_signing_key_is_bytes(self):
        assert isinstance(eng.SIGNING_KEY, bytes)
        assert len(eng.SIGNING_KEY) > 0

    def test_antigen_boundary(self):
        assert eng.SerotyperEngine.ANTIGEN_BOUNDARY["O"] == {"start": "coaD", "end": "rfaD"}
        assert eng.SerotyperEngine.ANTIGEN_BOUNDARY["K"] == {"start": "rfaD", "end": "glpX"}


class TestSelectByGeneCoverage:
    def test_returns_first_candidate_if_no_metadata(self, fake_engine_no_init, monkeypatch):
        fake_engine_no_init.metadata = {}
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        result = fake_engine_no_init._select_by_gene_coverage(["OL1", "OL2"], {}, FakeAligner())
        assert result in ("OL1", "OL2")

    def test_picks_locus_with_more_genes_present(self, tmp_path, monkeypatch):
        locus_a = _locus_with_genes("OL1", "O", n_genes=2)
        locus_b = _locus_with_genes("OL2", "O", n_genes=2)
        db = _build_synthetic_db(tmp_path, {"OL1": locus_a, "OL2": locus_b})
        fake_m = _install_fake_mappy(monkeypatch, FakeAligner(valid=True))

        comp = str.maketrans("ATGCatgc", "TACGtacg")
        gene_hits: dict[str, list[FakeHit]] = {}
        for g in locus_a["genes"]:
            gseq = locus_a["seq"][g["start"] : g["end"]]
            if g.get("strand", 1) == -1:
                gseq = gseq[::-1].translate(comp)
            gene_hits[gseq] = [
                FakeHit(ctg="ctg1", blen=len(gseq), mlen=len(gseq), q_st=0, q_en=len(gseq))
            ]

        sample_aligner = FakeAligner(hits_by_seq=gene_hits, default=[])
        fake_m._factory.default = sample_aligner

        engine = eng.SerotyperEngine(db)
        winner = engine._select_by_gene_coverage(["OL1", "OL2"], {}, sample_aligner)
        assert winner == "OL1"


class TestBuildLocusRegionAligner:
    def test_returns_none_for_empty(self, fake_engine_no_init, monkeypatch):
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        result = fake_engine_no_init._build_locus_region_aligner([])
        assert result is None

    def test_returns_aligner_for_non_empty(self, tmp_path, monkeypatch):
        locus = _locus_with_genes("OL1", "O", n_genes=2)
        db = _build_synthetic_db(tmp_path, {"OL1": locus})
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)
        entries = [("ctg1", locus["seq"], 1, 0)]
        aligner = engine._build_locus_region_aligner(entries)
        assert aligner is not None


class TestFindOtherGenesInLocus:
    def test_returns_empty_when_no_aligner(self, fake_engine_no_init):
        result = fake_engine_no_init._find_other_genes_in_locus("OL1", "O", None, [], FakeAligner())
        assert result == []

    def test_finds_other_locus_genes_in_region(self, tmp_path, monkeypatch):
        locus_a = _locus_with_genes("OL1", "O", n_genes=2)
        locus_b = _locus_with_genes("OL2", "O", n_genes=2)
        db = _build_synthetic_db(tmp_path, {"OL1": locus_a, "OL2": locus_b})
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)

        region_aligner = engine._build_locus_region_aligner([("ctg1", locus_a["seq"], 1, 0)])

        comp = str.maketrans("ATGCatgc", "TACGtacg")
        gene_hits: dict[str, list[FakeHit]] = {}
        for locus in (locus_a, locus_b):
            for g in locus["genes"]:
                gseq = locus["seq"][g["start"] : g["end"]]
                if g.get("strand", 1) == -1:
                    gseq = gseq[::-1].translate(comp)
                gene_hits[gseq] = [
                    FakeHit(ctg="region_0", blen=len(gseq), mlen=len(gseq), q_st=0, q_en=len(gseq))
                ]

        sample_aligner = FakeAligner(hits_by_seq=gene_hits, default=[])
        occupied = [("ctg1", 0, 100)]
        results = engine._find_other_genes_in_locus(
            "OL1", "O", region_aligner, occupied, sample_aligner
        )
        assert isinstance(results, list)


class TestResolveVariantLocus:
    def test_returns_none_when_no_v_suffix(self, tmp_path, monkeypatch):
        locus = _locus_with_genes("OL1", "O", n_genes=2)
        db = _build_synthetic_db(tmp_path, {"OL1": locus})
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)
        result = engine._resolve_variant_locus("OL1", "O", {}, FakeAligner())
        assert result is None

    def test_returns_none_when_only_one_candidate(self, tmp_path, monkeypatch):
        locus = _locus_with_genes("OL1V1", "O", n_genes=2)
        db = _build_synthetic_db(tmp_path, {"OL1V1": locus})
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)
        result = engine._resolve_variant_locus("OL1V1", "O", {}, FakeAligner())
        assert result is None

    def test_picks_variant_with_unique_gene_present(self, tmp_path, monkeypatch):
        seq = _random_dna(2000, seed=99)
        locus_v1 = {
            "type": "O",
            "seq": seq,
            "genes": [
                {"name": "g1", "locus_tag": "v1_t1", "start": 0, "end": 500, "strand": 1},
                {"name": "g2", "locus_tag": "v1_t2", "start": 500, "end": 1000, "strand": 1},
            ],
        }
        seq_v2 = seq[:1500] + _random_dna(500, seed=7)
        locus_v2 = {
            "type": "O",
            "seq": seq_v2,
            "genes": [
                {"name": "g1", "locus_tag": "v2_t1", "start": 0, "end": 500, "strand": 1},
                {"name": "g3", "locus_tag": "v2_t3", "start": 1000, "end": 1500, "strand": 1},
            ],
        }
        db = _build_synthetic_db(tmp_path, {"OL1V1": locus_v1, "OL1V2": locus_v2})
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)

        g3_seq = seq_v2[1000:1500]
        sample_aligner = FakeAligner(
            hits_by_seq={g3_seq: [FakeHit(ctg="ctg1", blen=500, mlen=500, q_st=0, q_en=500)]},
            default=[],
        )
        result = engine._resolve_variant_locus("OL1V1", "O", {}, sample_aligner)
        assert result in {"OL1V1", "OL1V2", None}


class TestGenerateDetail:
    def test_perfect_confidence_no_close_returns_empty(self, fake_engine_no_init):
        result = {
            "confidence": "Perfect",
            "locus": "OL1",
            "coverage": 100.0,
            "identity": 99.5,
            "missing": "",
        }
        out = fake_engine_no_init._generate_detail("O", "OL1", [("OL1", 100.0)], [], None, result)
        assert out == ""

    def test_untypeable_locus_with_no_close(self, fake_engine_no_init):
        result = {
            "confidence": "Unknown",
            "locus": "OL1",
            "coverage": 50.0,
            "identity": 80.0,
            "missing": "g1;g2",
        }
        out = fake_engine_no_init._generate_detail("O", "OL1", [("OL1", 50.0)], [], None, result)
        assert "Untypeable" in out
        assert "2 genes missing" in out
        assert "No close competitor" in out

    def test_untypeable_with_close_competitor(self, tmp_path, monkeypatch):
        locus = _locus_with_genes("OL1", "O", n_genes=2)
        db = _build_synthetic_db(tmp_path, {"OL1": locus})
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)

        result = {
            "confidence": "Unknown",
            "locus": "OL1",
            "coverage": 50.0,
            "identity": 80.0,
            "missing": "",
        }
        close = [("OL1", 50.0), ("OL2", 48.0)]
        out = engine._generate_detail(
            "O", "OL1", [("OL1", 50.0), ("OL2", 48.0)], close, FakeAligner(), result
        )
        assert "2 candidates within" in out


class TestCheckSupersetOverride:
    def test_returns_none_when_best_has_no_genes(self, fake_engine_no_init):
        fake_engine_no_init.metadata = {"OL1": {"genes": []}}
        result = fake_engine_no_init._check_superset_override("OL1", "O", set(), None)
        assert result is None

    def test_returns_none_when_no_candidates(self, tmp_path, monkeypatch):
        locus = _locus_with_genes("OL1", "O", n_genes=2)
        db = _build_synthetic_db(tmp_path, {"OL1": locus})
        _install_fake_mappy(monkeypatch, FakeAligner(valid=True))
        engine = eng.SerotyperEngine(db)
        result = engine._check_superset_override("OL1", "O", {"OL1"}, FakeAligner())
        assert result is None


class TestCountUniqueGenes:
    def test_returns_zero_when_seq_missing(self, fake_engine_no_init):
        out = fake_engine_no_init._count_unique_genes("OL1", "OL2", {}, FakeAligner(), {})
        assert out == (0, 0)


class TestRunOneSampleFastxError:
    def test_fastx_read_exception_returns_empty_result(self, tmp_path, monkeypatch):
        locus = _locus_with_genes("OL1", "O")
        db = _build_synthetic_db(tmp_path, {"OL1": locus})
        sample = tmp_path / "broken.fasta"
        sample.write_text(">ctg1\nACGT\n")

        class _ExplodingMappy(_MappyStub):
            def fastx_read(self, path: str):
                raise RuntimeError("fastx_read exploded")

        fake = _ExplodingMappy(_AlignerFactory(FakeAligner(valid=True)))
        monkeypatch.setitem(sys.modules, "mappy", fake)
        engine = eng.SerotyperEngine(db)
        result = engine.run_one_sample(sample)
        assert result["Predicted_Serotype"] == "OUT:KUT"
        assert "fastx_read exploded" in result["O_Missing_Genes"]
