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


def test_0035_uses_uuid_columns_for_stock_ai_extraction_foreign_keys() -> None:
    body = _read("migrations/versions/0035_s12_ai_preload_extractions.py")

    assert 'sa.Column("id", sa.UUID(), nullable=False)' in body
    assert 'sa.Column("tenant_id", sa.UUID(), nullable=False)' in body
    assert 'sa.Column("store_id", sa.UUID(), nullable=False)' in body
    assert 'sa.Column("created_by_user_id", sa.UUID(), nullable=True)' in body
    assert 'sa.Column("preload_session_id", sa.UUID(), nullable=True)' in body
    assert 'sa.Column("extraction_id", sa.UUID(), nullable=False)' in body
    assert 'sa.String(length=36)' not in body


def test_stock_ai_model_fk_columns_match_referenced_id_types() -> None:
    from app.aris3.db.models import PreloadSession, StockAiExtraction, StockAiExtractionFile, Store, Tenant, User

    assert type(StockAiExtraction.id.type) is type(Tenant.id.type)
    assert type(StockAiExtraction.tenant_id.type) is type(Tenant.id.type)
    assert type(StockAiExtraction.store_id.type) is type(Store.id.type)
    assert type(StockAiExtraction.created_by_user_id.type) is type(User.id.type)
    assert type(StockAiExtraction.preload_session_id.type) is type(PreloadSession.id.type)
    assert type(StockAiExtractionFile.extraction_id.type) is type(StockAiExtraction.id.type)
