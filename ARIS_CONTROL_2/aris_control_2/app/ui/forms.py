from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class FormStatus(str, Enum):
    IDLE = "idle"
    DIRTY = "dirty"
    VALID = "valid"
    SUBMITTING = "submitting"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class FormResult:
    values: dict[str, Any]
    field_errors: dict[str, str]

    @property
    def first_invalid_field(self) -> str | None:
        return next(iter(self.field_errors), None)

    @property
    def is_valid(self) -> bool:
        return len(self.field_errors) == 0


@dataclass
class FormState:
    status: FormStatus = FormStatus.IDLE
    submit_enabled: bool = False
    submit_disabled_reason: str = "Completa los campos requeridos."


def _normalize_required_text(value: str | None) -> str:
    return (value or "").strip()


def validate_tenant_name(name: str | None) -> FormResult:
    normalized_name = _normalize_required_text(name)
    field_errors: dict[str, str] = {}
    if not normalized_name:
        field_errors["name"] = "Nombre es obligatorio."
    elif len(normalized_name) < 1:
        field_errors["name"] = "Nombre debe tener al menos 1 carácter."
    elif len(normalized_name) > 255:
        field_errors["name"] = "Nombre no puede exceder 255 caracteres."
    return FormResult(values={"name": normalized_name}, field_errors=field_errors)


def validate_store_form(name: str | None, tenant_id: str | None) -> FormResult:
    normalized_name = _normalize_required_text(name)
    field_errors: dict[str, str] = {}
    if not tenant_id:
        field_errors["tenant_id"] = "Selecciona tenant antes de crear/editar store."
    if not normalized_name:
        field_errors["name"] = "Store name es obligatorio."
    elif len(normalized_name) > 255:
        field_errors["name"] = "Store name no puede exceder 255 caracteres."
    return FormResult(values={"name": normalized_name}, field_errors=field_errors)


def validate_user_form(email: str | None, password: str | None, tenant_id: str | None, store_id: str | None) -> FormResult:
    normalized_email = _normalize_required_text(email).lower()
    normalized_password = _normalize_required_text(password)
    normalized_store_id = _normalize_required_text(store_id) or None

    field_errors: dict[str, str] = {}
    if not tenant_id:
        field_errors["tenant_id"] = "Selecciona tenant antes de crear/editar user."
    if not normalized_email:
        field_errors["email"] = "Email es obligatorio."
    elif len(normalized_email) < 3:
        field_errors["email"] = "Email debe tener al menos 3 caracteres."
    elif len(normalized_email) > 255:
        field_errors["email"] = "Email no puede exceder 255 caracteres."
    elif not EMAIL_REGEX.match(normalized_email):
        field_errors["email"] = "Email inválido. Usa formato usuario@dominio.com."

    if not normalized_password:
        field_errors["password"] = "Password es obligatorio."
    elif len(normalized_password) < 8:
        field_errors["password"] = "Password debe tener al menos 8 caracteres."
    elif len(normalized_password) > 255:
        field_errors["password"] = "Password no puede exceder 255 caracteres."

    return FormResult(
        values={"email": normalized_email, "password": normalized_password, "store_id": normalized_store_id},
        field_errors=field_errors,
    )


def build_form_state(result: FormResult) -> FormState:
    if result.is_valid:
        return FormState(status=FormStatus.VALID, submit_enabled=True, submit_disabled_reason="")

    first_invalid_field = result.first_invalid_field or "formulario"
    return FormState(
        status=FormStatus.DIRTY,
        submit_enabled=False,
        submit_disabled_reason=f"Corrige '{first_invalid_field}' antes de enviar.",
    )


def map_api_validation_errors(error_details: Any) -> dict[str, str]:
    if not error_details:
        return {}

    mapped: dict[str, str] = {}
    if isinstance(error_details, dict):
        if isinstance(error_details.get("errors"), dict):
            for key, value in error_details["errors"].items():
                mapped[str(key)] = str(value)
        for key, value in error_details.items():
            if key == "errors":
                continue
            if isinstance(value, str):
                mapped[str(key)] = value
            elif isinstance(value, list) and value and isinstance(value[0], str):
                mapped[str(key)] = value[0]
    elif isinstance(error_details, list):
        for item in error_details:
            if not isinstance(item, dict):
                continue
            field = item.get("field") or item.get("loc")
            message = item.get("message") or item.get("msg")
            if isinstance(field, list):
                field = field[-1] if field else None
            if field and message:
                mapped[str(field)] = str(message)
    return mapped
