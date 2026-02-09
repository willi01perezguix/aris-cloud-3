from __future__ import annotations

import pytest

from aris3_client_sdk.stock_validation import (
    ClientValidationError,
    normalize_epc,
    validate_epc_24_hex,
    validate_import_epc_line,
    validate_import_sku_line,
    validate_migration_line,
)


def test_epc_normalization() -> None:
    assert normalize_epc("   ") is None
    assert normalize_epc(" a1b2c3d4e5f6a1b2c3d4e5f6 ") == "A1B2C3D4E5F6A1B2C3D4E5F6"


def test_epc_format_validation() -> None:
    validate_epc_24_hex("A" * 24)
    with pytest.raises(ValueError):
        validate_epc_24_hex("a" * 24)
    with pytest.raises(ValueError):
        validate_epc_24_hex("A" * 23)


def test_validate_import_epc_line_success() -> None:
    line = validate_import_epc_line(
        {
            "sku": "SKU-1",
            "description": "Blue",
            "var1_value": "Blue",
            "var2_value": "L",
            "epc": "a" * 24,
            "location_code": "LOC-1",
            "pool": "P1",
            "status": "RFID",
            "location_is_vendible": True,
            "qty": 1,
        },
        0,
    )
    assert line.epc == "A" * 24


def test_validate_import_epc_line_invalid_qty() -> None:
    with pytest.raises(ClientValidationError):
        validate_import_epc_line(
            {
                "sku": "SKU-1",
                "epc": "A" * 24,
                "location_code": "LOC-1",
                "pool": "P1",
                "status": "RFID",
                "location_is_vendible": True,
                "qty": 2,
            },
            1,
        )


def test_validate_import_sku_line_epc_disallowed() -> None:
    with pytest.raises(ClientValidationError):
        validate_import_sku_line(
            {
                "sku": "SKU-1",
                "epc": "A" * 24,
                "location_code": "LOC-1",
                "pool": "P1",
                "status": "PENDING",
                "location_is_vendible": True,
                "qty": 1,
            },
            2,
        )


def test_validate_migration_line_status_required() -> None:
    with pytest.raises(ClientValidationError):
        validate_migration_line(
            {
                "epc": "A" * 24,
                "data": {
                    "sku": "SKU-1",
                    "status": "RFID",
                    "location_code": "LOC-1",
                    "pool": "P1",
                    "location_is_vendible": True,
                },
            },
            0,
        )
