from __future__ import annotations


def test_major_modules_import() -> None:
    import aris3_client_sdk.models_stock  # noqa: F401
    import aris3_client_sdk.models_pos_sales  # noqa: F401
    import aris3_client_sdk.models_pos_cash  # noqa: F401
    import aris3_client_sdk.models_transfers  # noqa: F401
    import aris3_client_sdk.models_inventory_counts  # noqa: F401
    import aris3_client_sdk.models_reports  # noqa: F401
    import aris3_client_sdk.models_exports  # noqa: F401
    import aris3_client_sdk.models_media  # noqa: F401
