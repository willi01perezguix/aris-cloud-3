from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_0024_uses_guid_for_tenant_fk_columns() -> None:
    body = _read("migrations/versions/0024_s8dx_tenant_purge_lock.py")

    assert 'sa.Column("id", GUID(), nullable=False)' in body
    assert 'sa.Column("tenant_id", GUID(), nullable=False)' in body
    assert 'down_revision = "0023_s8dx_stock_items_contract_guard"' in body


def test_post_s4d6_chain_is_linear_until_0024() -> None:
    r0017 = _read("migrations/versions/0017_s4d7_pos_returns_search.py")
    r0018 = _read("migrations/versions/0018_sprint8_dayx_stock_base_prices.py")

    assert 'down_revision = "0017_s4d6_tenant_store_user_hard"' in r0017
    assert 'down_revision = "0017_s4d7_pos_returns_search"' in r0018


def test_0024_guid_maps_to_postgres_uuid_type() -> None:
    import importlib.util
    from sqlalchemy.dialects import postgresql

    path = REPO_ROOT / "migrations/versions/0024_s8dx_tenant_purge_lock.py"
    spec = importlib.util.spec_from_file_location("mig0024", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    guid_type = module.GUID()
    impl = guid_type.load_dialect_impl(postgresql.dialect())
    assert impl.__class__.__name__ == "PGUuid"
