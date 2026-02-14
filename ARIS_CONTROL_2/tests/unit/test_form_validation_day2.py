from aris_control_2.app.ui.forms import (
    FormStatus,
    build_form_state,
    map_api_validation_errors,
    validate_store_form,
    validate_tenant_name,
    validate_user_form,
)


def test_validate_tenant_name_trims_and_requires_value() -> None:
    result = validate_tenant_name("   ")

    assert result.is_valid is False
    assert result.field_errors["name"] == "Nombre es obligatorio."


def test_validate_store_form_requires_tenant_context() -> None:
    result = validate_store_form(name="Main Store", tenant_id=None)

    assert result.is_valid is False
    assert "tenant_id" in result.field_errors


def test_validate_user_form_normalizes_email_and_trims_password() -> None:
    result = validate_user_form(
        email="  USER@Example.COM  ",
        password="   supersecret   ",
        tenant_id="tenant-1",
        store_id="  store-1  ",
    )

    assert result.is_valid is True
    assert result.values["email"] == "user@example.com"
    assert result.values["password"] == "supersecret"
    assert result.values["store_id"] == "store-1"


def test_validate_user_form_rejects_invalid_email() -> None:
    result = validate_user_form(
        email="invalid-email",
        password="supersecret",
        tenant_id="tenant-1",
        store_id=None,
    )

    assert result.is_valid is False
    assert "formato" in result.field_errors["email"]


def test_build_form_state_blocks_submit_when_invalid() -> None:
    result = validate_store_form(name="", tenant_id="tenant-1")

    state = build_form_state(result)

    assert state.status == FormStatus.DIRTY
    assert state.submit_enabled is False
    assert "Corrige" in state.submit_disabled_reason


def test_map_api_validation_errors_handles_backend_422_shapes() -> None:
    details = {
        "errors": {
            "email": "ya existe",
            "password": "demasiado corto",
        },
        "store_id": ["store inválida"],
    }

    mapped = map_api_validation_errors(details)

    assert mapped["email"] == "ya existe"
    assert mapped["password"] == "demasiado corto"
    assert mapped["store_id"] == "store inválida"
