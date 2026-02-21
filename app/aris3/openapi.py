from copy import deepcopy

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


VALIDATION_ERROR_REF = "#/components/schemas/ValidationErrorResponse"
NOT_FOUND_ERROR_REF = "#/components/schemas/NotFoundErrorResponse"
CONFLICT_ERROR_REF = "#/components/schemas/ConflictErrorResponse"

TAG_METADATA = [
    {"name": "Admin Tenants", "description": "Tenant lifecycle administration (list, create, update, delete, status actions)."},
    {"name": "Admin Stores", "description": "Store administration endpoints, including tenant-scoped creation and lifecycle actions."},
    {"name": "Admin Users", "description": "User administration endpoints (CRUD plus operational actions such as status/role/password updates)."},
    {
        "name": "Admin Access Control",
        "description": "Administrative access-control management for role templates, overlays, and overrides with scope resolved from JWT/context when not explicit.",
    },
    {"name": "Admin Settings", "description": "Administrative runtime settings endpoints."},
    {
        "name": "Access Control Scoped",
        "description": "Scope-aware access-control endpoints for catalog/policy retrieval and effective permission resolution.",
    },
]


_ERROR_PROPS = {
    "code": {"type": "string"},
    "message": {"type": "string"},
    "details": {"type": "object", "nullable": True, "additionalProperties": True},
    "trace_id": {"type": "string", "nullable": True, "example": "trace-123"},
}

ERROR_RESPONSE_SCHEMAS = {
    "ErrorResponse": {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            **_ERROR_PROPS,
            "code": {"type": "string", "example": "NOT_FOUND"},
            "message": {"type": "string", "example": "Resource not found"},
        },
    },
    "NotFoundError": {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            **_ERROR_PROPS,
            "code": {"type": "string", "example": "NOT_FOUND"},
            "message": {"type": "string", "example": "Resource not found"},
        },
    },
    "ConflictError": {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            **_ERROR_PROPS,
            "code": {"type": "string", "example": "CONFLICT"},
            "message": {"type": "string", "example": "Resource conflict"},
        },
    },
    "ValidationError": {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            **_ERROR_PROPS,
            "code": {"type": "string", "example": "VALIDATION_ERROR"},
            "message": {"type": "string", "example": "Validation error"},
            "details": {
                "type": "object",
                "properties": {
                    "errors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string", "nullable": True},
                                "message": {"type": "string"},
                                "type": {"type": "string"},
                                "loc": {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]}, "nullable": True},
                                "input": {"nullable": True},
                                "ctx": {"type": "object", "nullable": True, "additionalProperties": True},
                            },
                        },
                    }
                },
                "nullable": True,
            },
        },
        "example": {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": {
                "errors": [
                    {"field": "field_name", "message": "Invalid value", "type": "value_error"}
                ]
            },
            "trace_id": "trace-123",
        },
    },
    "NotFoundErrorResponse": {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            **_ERROR_PROPS,
            "code": {"type": "string", "example": "NOT_FOUND"},
            "message": {"type": "string", "example": "Resource not found"},
        },
    },
    "ConflictErrorResponse": {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            **_ERROR_PROPS,
            "code": {"type": "string", "example": "CONFLICT"},
            "message": {"type": "string", "example": "Resource conflict"},
        },
    },
    "ValidationErrorResponse": {"$ref": "#/components/schemas/ValidationError"},
}


def _operation_id(method: str, path: str) -> str:
    normalized = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    return f"{method}_{normalized}"


def _assign_tag(path: str) -> str | None:
    if path.startswith("/aris3/access-control"):
        return "Access Control Scoped"
    if path.startswith("/aris3/admin/access-control"):
        return "Admin Access Control"
    if path.startswith("/aris3/admin/tenants"):
        return "Admin Tenants"
    if path.startswith("/aris3/admin/stores"):
        return "Admin Stores"
    if path.startswith("/aris3/admin/users"):
        return "Admin Users"
    if path.startswith("/aris3/admin/settings"):
        return "Admin Settings"
    return None


def _is_explicit_scope_path(path: str) -> bool:
    return any(token in path for token in ("{tenant_id}", "{store_id}", "{user_id}"))


def _apply_access_control_descriptions(path: str, method: str, operation: dict) -> None:
    hierarchy = (
        "Permission hierarchy: 1) Role Template, 2) Tenant/Store overlays (allow/deny), "
        "3) User overrides, 4) Effective permissions."
    )

    if path.startswith("/aris3/access-control"):
        if _is_explicit_scope_path(path):
            context = "Scoped endpoint with explicit subject/scope identifiers in the request path."
        else:
            if method == "get":
                context = "Scoped endpoint resolved from authenticated context and optional query parameters."
            else:
                context = "Scoped endpoint resolved from authenticated context and optional request body/query parameters."
        operation["description"] = f"{context}\n\n{hierarchy}"

    if path.startswith("/aris3/admin/access-control"):
        operation["description"] = (
            "Admin endpoint: tenant/store scope is resolved from JWT/context unless explicit path/query/body parameters override it."
            f"\n\n{hierarchy}"
        )

    if path == "/aris3/admin/access-control/permission-catalog":
        operation["deprecated"] = True
        operation["description"] = (
            "Deprecated admin alias for permission catalog. Prefer `/aris3/access-control/permission-catalog`."
            f"\n\n{hierarchy}"
        )


def _not_found_description(path: str) -> str:
    if "{store_id}" in path:
        return "Store not found"
    if "{user_id}" in path:
        return "User not found"
    if "{tenant_id}" in path:
        return "Tenant not found"
    return "Resource not found"


def _apply_error_responses(path: str, method: str, operation: dict) -> None:
    if not (path.startswith("/aris3/admin") or path.startswith("/aris3/access-control")):
        return

    responses = operation.setdefault("responses", {})
    responses["422"] = {
        "description": "Validation error",
        "content": {"application/json": {"schema": {"$ref": VALIDATION_ERROR_REF}}},
    }

    if method in {"post", "put", "patch", "delete"}:
        responses.setdefault("404", {"description": _not_found_description(path)})
        responses.setdefault("409", {"description": "Resource conflict"})

    if "404" in responses:
        not_found_message = _not_found_description(path)
        responses["404"]["description"] = not_found_message
        responses["404"]["content"] = {
            "application/json": {
                "schema": {"$ref": NOT_FOUND_ERROR_REF},
                "example": {"code": "NOT_FOUND", "message": not_found_message, "details": None, "trace_id": "trace-123"},
            }
        }

    if "409" in responses:
        responses["409"]["description"] = "Resource conflict"
        responses["409"]["content"] = {
            "application/json": {
                "schema": {"$ref": CONFLICT_ERROR_REF},
                "example": {"code": "CONFLICT", "message": "Resource conflict", "details": None, "trace_id": "trace-123"},
            }
        }


def harden_openapi_schema(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(title=app.title, version="1.0.0", routes=app.routes)
    schema["tags"] = TAG_METADATA
    schema.setdefault("components", {}).setdefault("schemas", {}).update(deepcopy(ERROR_RESPONSE_SCHEMAS))

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            tag = _assign_tag(path)
            if tag:
                operation["tags"] = [tag]
            operation["operationId"] = _operation_id(method, path)
            _apply_access_control_descriptions(path, method, operation)
            _apply_error_responses(path, method, operation)

    app.openapi_schema = schema
    return app.openapi_schema
