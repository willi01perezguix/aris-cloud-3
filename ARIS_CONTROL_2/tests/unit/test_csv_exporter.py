from aris_control_2.app.export.csv_exporter import export_current_view


def test_csv_exporter_creates_valid_csv(tmp_path) -> None:
    out_dir = tmp_path / "exports"
    rows = [{"id": "1", "name": "Main"}]

    path = export_current_view("stores", rows, headers=["id", "name"], output_dir=str(out_dir))

    assert path.exists()
    content = path.read_text(encoding="utf-8-sig")
    assert "id,name" in content
    assert "1,Main" in content
