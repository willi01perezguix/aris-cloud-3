import pytest

from app.aris3.db import schema_guard


class _FakeResult:
    def __init__(self, revisions):
        self._revisions = revisions

    def scalars(self):
        return self

    def all(self):
        return self._revisions


class _FakeConn:
    def __init__(self, revisions):
        self._revisions = revisions

    def execute(self, _query):
        return _FakeResult(self._revisions)


class _FakeEngine:
    def __init__(self, revisions):
        self._revisions = revisions

    def connect(self):
        conn = _FakeConn(self._revisions)

        class _Ctx:
            def __enter__(self_inner):
                return conn

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _Ctx()


class _FakeScriptDirectory:
    def __init__(self, heads):
        self._heads = heads

    def get_heads(self):
        return self._heads


def test_schema_guard_skips_sqlite(monkeypatch):
    monkeypatch.setattr(schema_guard.settings, "SCHEMA_DRIFT_GUARD_ENABLED", True)
    monkeypatch.setattr(schema_guard.settings, "DATABASE_URL", "sqlite+pysqlite:///./local.db")

    def _should_not_be_called(_config):
        raise AssertionError("alembic lookup should be skipped for sqlite")

    monkeypatch.setattr(schema_guard.ScriptDirectory, "from_config", _should_not_be_called)

    schema_guard.verify_schema_alignment()


def test_schema_guard_raises_on_revision_mismatch(monkeypatch):
    monkeypatch.setattr(schema_guard.settings, "SCHEMA_DRIFT_GUARD_ENABLED", True)
    monkeypatch.setattr(schema_guard.settings, "SCHEMA_DRIFT_GUARD_ENFORCE", True)
    monkeypatch.setattr(schema_guard.settings, "DATABASE_URL", "postgresql+psycopg://db")

    monkeypatch.setattr(schema_guard.ScriptDirectory, "from_config", lambda _config: _FakeScriptDirectory(["0026_head"]))
    monkeypatch.setattr(schema_guard, "engine", _FakeEngine(["0023_old"]))

    with pytest.raises(RuntimeError, match="Schema drift detected"):
        schema_guard.verify_schema_alignment()
