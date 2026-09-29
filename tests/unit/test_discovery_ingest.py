"""Tests for discovery-run artifacts and their GOM ingestion.

run_pangenome must persist summary.json; the differential_genes handler must
persist per-source JSON; scripts/ingest_results.py::ingest_discovery must
register both as ANALYSIS cohort objects with file artifacts and events
(idempotent, content-versioned).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

_SPEC = importlib.util.spec_from_file_location(
    "ingest_results", _PROJECT_ROOT / "scripts" / "ingest_results.py"
)
ingest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ingest)

from hermes_bacmap.services.genome_object_service import (  # noqa: E402
    GenomeObjectService,
    ObjectType,
)

GAPIT_HEADER = (
    "#FILE\tSEQUENCE\tSTART\tEND\tSTRAND\tGENE\tCOVERAGE\tCOVERAGE_MAP\tGAPS\t"
    "%COVERAGE\t%IDENTITY\tDATABASE\tACCESSION\tPRODUCT\tRESISTANCE"
)


def _gos(tmp_path: Path) -> GenomeObjectService:
    return GenomeObjectService(tmp_path / "gom.sqlite")


def _annotation(sample: str) -> None:
    pass


def _make_pangenome_summary(results: Path, samples: list[str], n_clusters: int = 5) -> None:
    p = results / "pangenome"
    p.mkdir(parents=True, exist_ok=True)
    matrix = str(p / "presence_matrix.parquet")
    payload = {
        "analysis_type": "pangenome",
        "method": "mmseqs2_linclust",
        "database": {"name": "mmseqs2_easy-linclust", "version": "unknown"},
        "samples": samples,
        "result": {"total_clusters": n_clusters, "matrix_path": matrix},
    }
    (p / "summary.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (p / "presence_matrix.parquet").write_bytes(b"parquet-bytes")


def _make_differential(results: Path, source: str, gene: str = "tdh") -> None:
    p = results / "analytics"
    p.mkdir(parents=True, exist_ok=True)
    payload = {
        "analysis_type": "differential_genes",
        "method": "fisher_exact_bh",
        "source": source,
        "result": {"n_a": 4, "n_b": 4, "genes": [{"gene": gene, "p_value": 0.0286}]},
    }
    (p / f"differential_{source}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


class TestPangenomeSummaryWrite:
    def test_run_pangenome_persists_summary_json(self, tmp_path):
        from hermes_bacmap.analysis.pangenome import run_pangenome

        for sample in ("SAM1", "SAM2"):
            d = tmp_path / sample / "annotation"
            d.mkdir(parents=True)
            (d / "annotation.json").write_text(
                json.dumps(
                    {
                        "sample_id": sample,
                        "features": [
                            {
                                "locus_tag": "cds001",
                                "ftype": "CDS",
                                "gene": "gapA",
                                "protein_seq": "MKVL",
                            }
                        ],
                    }
                )
            )

        def fake_cluster(fasta, out_prefix, min_seq_id=0.9, coverage=0.8):
            tsv = Path(f"{out_prefix}_cluster.tsv")
            tsv.write_text("SAM1__cds001\tSAM1__cds001\nSAM1__cds001\tSAM2__cds001\n")
            return tsv

        with patch("hermes_bacmap.analysis.pangenome.Mmseqs2Backend") as backend_cls:
            backend_cls.return_value.cluster = fake_cluster
            result = run_pangenome(["SAM1", "SAM2"], tmp_path, tmp_path / "pangenome")

        summary_path = tmp_path / "pangenome" / "summary.json"
        assert summary_path.exists()
        saved = json.loads(summary_path.read_text())
        assert saved == result.to_dict()
        assert saved["analysis_type"] == "pangenome"


class TestDifferentialFileWrite:
    def test_handler_persists_differential_json(self, tmp_path, monkeypatch):
        from hermes_bacmap.tools import differential_genes as handler

        for sample, genes in {
            "SAM-A1": ["geneX"],
            "SAM-A2": ["geneX"],
            "SAM-B1": ["geneY"],
            "SAM-B2": ["geneY"],
        }.items():
            d = tmp_path / sample / "amr"
            d.mkdir(parents=True)
            rows = [
                f"results/{sample}/c.fasta\tctg1\t1\t99\t+\t{g}\t1:0-99\t0/99\t0/0\t"
                f"100.0\t99.5\tcard\tX1\tp\t"
                for g in genes
            ]
            (d / "gapit_card.tsv").write_text(GAPIT_HEADER + "\n" + "\n".join(rows) + "\n")

        monkeypatch.setattr("hermes_bacmap.tools.discovery._RESULTS_DIR", tmp_path)

        args = {"group_a": ["SAM-A1", "SAM-A2"], "group_b": ["SAM-B1", "SAM-B2"]}
        out = json.loads(handler(args))

        saved_path = tmp_path / "analytics" / "differential_gapit_card.json"
        assert saved_path.exists()
        saved = json.loads(saved_path.read_text())
        assert saved["analysis_type"] == "differential_genes"
        assert saved["result"]["n_a"] == 2
        assert out["analysis_type"] == "differential_genes"


class TestIngestDiscovery:
    def test_ingests_pangenome_summary(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest, "RESULTS_DIR", tmp_path)
        _make_pangenome_summary(tmp_path, ["SAM1", "SAM2"])
        gos = _gos(tmp_path)

        oids = ingest.ingest_discovery(gos)

        assert len(oids) == 1
        objs = [
            o for o in gos.list_by_type(ObjectType.ANALYSIS) if o.strain_id == "cohort:pangenome"
        ]
        assert len(objs) == 1
        assert objs[0].payload["analysis_type"] == "pangenome"
        assert objs[0].payload["samples"] == ["SAM1", "SAM2"]

        events = gos.list_events(oids[0])
        assert any(e.event_type == "pangenome_clustered" for e in events)

        artifacts = gos.list_file_artifacts(oids[0], 1)
        assert any(a.file_type == "pangenome_matrix" for a in artifacts)
        gos.close()

    def test_pangenome_idempotent_on_same_content(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest, "RESULTS_DIR", tmp_path)
        _make_pangenome_summary(tmp_path, ["SAM1", "SAM2"])
        gos = _gos(tmp_path)

        first = ingest.ingest_discovery(gos)
        second = ingest.ingest_discovery(gos)

        assert first and not second
        objs = [
            o for o in gos.list_by_type(ObjectType.ANALYSIS) if o.strain_id == "cohort:pangenome"
        ]
        assert len(objs) == 1
        gos.close()

    def test_pangenome_new_content_creates_v2(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest, "RESULTS_DIR", tmp_path)
        _make_pangenome_summary(tmp_path, ["SAM1", "SAM2"], n_clusters=5)
        gos = _gos(tmp_path)
        ingest.ingest_discovery(gos)

        _make_pangenome_summary(tmp_path, ["SAM1", "SAM2", "SAM3"], n_clusters=9)
        oids = ingest.ingest_discovery(gos)

        assert oids
        objs = sorted(
            (o for o in gos.list_by_type(ObjectType.ANALYSIS) if o.strain_id == "cohort:pangenome"),
            key=lambda o: o.version,
        )
        assert objs[-1].version == 2
        assert objs[-1].payload["result"]["total_clusters"] == 9
        gos.close()

    def test_ingests_differential_per_source(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest, "RESULTS_DIR", tmp_path)
        _make_differential(tmp_path, "gapit_card", gene="tdh")
        _make_differential(tmp_path, "gapit_vfdb", gene="vopQ")
        gos = _gos(tmp_path)

        oids = ingest.ingest_discovery(gos)

        assert len(oids) == 2
        strain_ids = {
            o.strain_id
            for o in gos.list_by_type(ObjectType.ANALYSIS)
            if o.strain_id.startswith("cohort:discovery-")
        }
        assert strain_ids == {"cohort:discovery-gapit_card", "cohort:discovery-gapit_vfdb"}

        card = next(
            o
            for o in gos.list_by_type(ObjectType.ANALYSIS)
            if o.strain_id == "cohort:discovery-gapit_card"
        )
        events = gos.list_events(card.object_id)
        assert any(e.event_type == "differential_computed" for e in events)
        gos.close()

    def test_no_discovery_files_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ingest, "RESULTS_DIR", tmp_path)
        gos = _gos(tmp_path)

        assert ingest.ingest_discovery(gos) == []
        gos.close()
