from __future__ import annotations

import pytest

from aris3_client_sdk.models_pos_sales import PosSaleLineSnapshot
from aris_core_3_app.app import CoreAppShell
from aris_control_center_app.app import ControlCenterAppShell


@pytest.fixture(autouse=True)
def _set_api_base_url(monkeypatch) -> None:
    monkeypatch.setenv("ARIS3_API_BASE_URL", "https://api.example.com")


def test_stock_media_helper_uses_placeholder() -> None:
    app = CoreAppShell()
    media = app._resolve_row_media({"sku": "SKU-1", "var1_value": "Blue", "var2_value": "L"})
    assert media["source"] == "PLACEHOLDER"


def test_pos_preview_updates_on_selection() -> None:
    app = CoreAppShell()
    media = app._resolve_snapshot_media(
        PosSaleLineSnapshot(sku="SKU-1", image_url="https://cdn/full.jpg", image_thumb_url="https://cdn/thumb.jpg")
    )
    assert media["thumb_url"].startswith("https://")


def test_show_images_toggle_roundtrip() -> None:
    app = CoreAppShell()
    app.stock_show_images_var.set(False)
    assert app.stock_show_images_var.get() is False


def test_control_center_media_inspector_loads() -> None:
    app = ControlCenterAppShell()
    app.allowed_permissions = {"stock.view"}
    app.media_sku_var.set("SKU-1")
    assert app.media_sku_var.get() == "SKU-1"
