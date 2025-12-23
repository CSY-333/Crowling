import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import yaml

from src.config import get_default_config_path
from src.main import parse_args, bootstrap_runtime


def _write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "cli_config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _search_override():
    return {
        "keywords": ["cli-alpha"],
        "date_range": {"start": "2025-02-01", "end": "2025-02-10"},
    }


def test_parse_args_uses_default_config_when_not_provided():
    args = parse_args([])
    assert args.config == str(get_default_config_path())
    assert args.resume_from_db is None


def test_bootstrap_runtime_prefers_resume_db_path(monkeypatch, tmp_path):
    config_path = _write_config(tmp_path, {"search": _search_override()})
    resume_db = tmp_path / "resume.db"

    class DummyDB:
        def __init__(self, path: str, wal_mode: bool):
            self.path = path
            self.wal_mode = wal_mode
            self.init_called = False

        def init_schema(self):
            self.init_called = True

    created = {}

    def fake_db(path, wal_mode):
        db = DummyDB(path, wal_mode)
        created["db"] = db
        return db

    monkeypatch.setattr("src.main.Database", fake_db)

    args = SimpleNamespace(config=str(config_path), resume_from_db=str(resume_db))
    context = bootstrap_runtime(args)

    assert context.db is created["db"]
    assert created["db"].path == str(resume_db)
    assert created["db"].wal_mode is True
    assert created["db"].init_called is True
    assert re.match(r"\d{8}_\d{6}", context.run_id)
    datetime.fromisoformat(context.snapshot_at)
