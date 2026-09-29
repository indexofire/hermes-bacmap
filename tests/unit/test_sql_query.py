"""Unit tests for the GOM SQL query tool (tools/sandbox.py::sql_query).

Read-only SELECT/WITH queries against the GOM SQLite database via ro URI;
write statements rejected; markdown table output.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from hermes_bacmap.services.genome_object_service import (  # noqa: E402
    GenomeObject,
    GenomeObjectService,
    ObjectType,
)
from hermes_bacmap.tools.sandbox import sql_query  # noqa: E402


def _seed_gom(db_path: Path) -> None:
    with GenomeObjectService(db_path) as gos:
        for i, sid in enumerate(("SAM-A1", "SAM-A2"), start=1):
            gos.create(
                GenomeObject(
                    object_id=str(uuid.uuid4()),
                    object_type=ObjectType.ANALYSIS,
                    version=1,
                    schema_version="0.1.0",
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                    created_by="test",
                    payload={
                        "analysis_type": "species_identification",
                        "method": "marker",
                        "database": {"name": "m", "version": "1"},
                        "result": {"species": "Salmonella", "confidence": "high"},
                        "x": i,
                    },
                    pipeline_version="p1",
                    database_versions={"markers": "v1"},
                    strain_id=sid,
                )
            )


class TestSqlQuery:
    def test_select_returns_markdown_rows(self, tmp_path, monkeypatch):
        db = tmp_path / "gom.sqlite"
        _seed_gom(db)
        monkeypatch.setattr("hermes_bacmap.tools.sandbox._DEFAULT_DB_PATH", db)

        sql = "SELECT strain_id, object_type FROM genome_objects ORDER BY strain_id"
        out = sql_query({"sql": sql})

        assert "SAM-A1" in out and "SAM-A2" in out
        assert "|" in out

    def test_write_rejected(self, tmp_path, monkeypatch):
        db = tmp_path / "gom.sqlite"
        _seed_gom(db)
        monkeypatch.setattr("hermes_bacmap.tools.sandbox._DEFAULT_DB_PATH", db)

        out = json.loads(sql_query({"sql": "DELETE FROM genome_objects"}))
        assert "error" in out

    def test_missing_db_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "hermes_bacmap.tools.sandbox._DEFAULT_DB_PATH", tmp_path / "missing.sqlite"
        )

        out = json.loads(sql_query({"sql": "SELECT 1"}))
        assert "error" in out

    def test_lists_core_tables_when_sql_empty(self, tmp_path, monkeypatch):
        db = tmp_path / "gom.sqlite"
        _seed_gom(db)
        monkeypatch.setattr("hermes_bacmap.tools.sandbox._DEFAULT_DB_PATH", db)

        out = sql_query({"sql": ""})

        assert "genome_objects" in out
        assert "events" in out
