from aris_control_2.app.context_store import restore_compatible_context, save_context
from aris_control_2.app.export.csv_exporter import export_current_view
from aris_control_2.app.ui.listing_view import ListingViewState, sort_rows


def test_sort_rows_by_selected_column_desc() -> None:
    rows = [{"name": "alice"}, {"name": "carol"}, {"name": "bob"}]

    ordered = sort_rows(rows, ListingViewState(visible_columns=["name"], sort_by="name", sort_dir="desc"))

    assert [item["name"] for item in ordered] == ["carol", "bob", "alice"]


def test_listing_view_persistence_roundtrip(tmp_path, monkeypatch) -> None:
    context_file = tmp_path / "operator-context.json"
    monkeypatch.setenv("ARIS3_OPERATOR_CONTEXT_PATH", str(context_file))

    save_context(
        session_fingerprint="SUPERADMIN:tenant-1",
        selected_tenant_id="tenant-1",
        filters_by_module={"users": {"status": "ACTIVE"}},
        pagination_by_module={"users": {"page": 2, "page_size": 20}},
        listing_view_by_module={"users": {"visible_columns": ["id"], "sort_by": "id", "sort_dir": "asc"}},
    )

    restored = restore_compatible_context(session_fingerprint="SUPERADMIN:tenant-1")

    assert restored["listing_view_by_module"]["users"]["visible_columns"] == ["id"]


def test_export_respects_filtered_rows_only_and_sanitizes_sensitive_data(tmp_path) -> None:
    out_dir = tmp_path / "exports"
    rows = [
        {"id": "u-1", "username": "alice", "token": "secret-1"},
        {"id": "u-2", "username": "bob", "token": "secret-2"},
    ]
    filtered_rows = [rows[0]]

    path = export_current_view(
        module="users",
        rows=filtered_rows,
        headers=["id", "username", "token"],
        output_dir=str(out_dir),
        tenant_id="tenant-1",
        filters={"q": "alice"},
    )

    content = path.read_text(encoding="utf-8-sig")
    assert "# filters: {'q': 'alice'}" in content
    assert "u-1,alice,—" in content
    assert "u-2" not in content
