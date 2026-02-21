from copy import deepcopy

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


ADMIN_ERROR_REF = "#/components/schemas/ErrorResponse"
ADMIN_VALIDATION_ERROR_REF = "#/components/schemas/ValidationErrorResponse"

TAG_METADATA = [
    {"name": "Admin Tenants", "description": "Tenant administration endpoints."},
    {"name": "Admin Stores", "description": "Store administration endpoints."},
    {"name": "Admin Users", "description": "User administration endpoints."},
    {"name": "Admin Access Control", "description": "Admin access-control endpoints with tenant/store scope resolved from JWT/context unless explicitly provided."},
    {"name": "Admin Settings", "description": "Administrative settings endpoints."},
    {"name": "Access Control (Scoped)", "description": "Scoped access-control endpoints with explicit tenant/store/user path parameters."},
]


ERROR_RESPONSE_SCHEMAS = {
    "ErrorResponse": {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            "code": {"type": "string", "example": "NOT_FOUND"},
            "message": {"type": "string", "example": "Resource not found"},
            "details": {"type": "object", "nullable": True, "additionalProperties": True},
            "trace_id": {"type": "string", "nullable": True, "example": "trace-123"},
        },
    },
    "ValidationErrorResponse": {
        "allOf": [
            {"$ref": "#/components/schemas/ErrorResponse"},
            {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "example": "VALIDATION_ERROR"},
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
                                    },
                                },
                            }
                        },
                        "nullable": True,
                    },
                },
            },
        ]
    },
    "NotFoundErrorResponse": {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            "code": {"type": "string", "example": "NOT_FOUND"},
            "message": {"type": "string", "example": "Resource not found"},
            "details": {"type": "object", "nullable": True, "additionalProperties": True},
            "trace_id": {"type": "string", "nullable": True, "example": "trace-123"},
        },
    },
    "ConflictErrorResponse": {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            "code": {"type": "string", "example": "CONFLICT"},
            "message": {"type": "string", "example": "Resource conflict"},
            "details": {"type": "object", "nullable": True, "additionalProperties": True},
            "trace_id": {"type": "string", "nullable": True, "example": "trace-123"},
        },
    },
}


def _operation_id(method: str, path: str) -> str:
    normalized = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    return f"{method}_{normalized}"


def _assign_tag(path: str) -> str | None:
    if path.startswith("/aris3/access-control"):
        return "Access Control (Scoped)"
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


def _apply_access_control_descriptions(path: str, method: str, operation: dict) -> None:
    hierarchy = (
        "Permission hierarchy: 1) Role Template, 2) Tenant/Store overlays (allow/deny), "
        "3) User overrides, 4) Effective permissions resolution."
    )
    if path.startswith("/aris3/access-control"):
        base = "Scoped endpoint: tenant/store/user scope is explicit in the request path."
        operation["description"] = f"{base}\n\n{hierarchy}"
    if path.startswith("/aris3/admin/access-control"):
        base = "Admin endpoint: tenant/store scope is resolved from JWT/context unless endpoint parameters explicitly override it."
        operation["description"] = f"{base}\n\n{hierarchy}"

    if path == "/aris3/admin/access-control/permission-catalog":
        operation["deprecated"] = True
        operation["description"] = (
            "Deprecated admin alias for permission catalog. Prefer `/aris3/access-control/permission-catalog`."
            "\n\n"
            f"{hierarchy}"
        )


def _apply_error_responses(path: str, operation: dict) -> None:
    if not (path.startswith("/aris3/admin") or path.startswith("/aris3/access-control")):
        return

    responses = operation.setdefault("responses", {})
    responses.setdefault("404", {"description": "Not found"})
    responses.setdefault("409", {"description": "Conflict"})
    responses.setdefault("422", {"description": "Validation error"})

    responses["404"]["content"] = {"application/json": {"schema": {"$ref": "#/components/schemas/NotFoundErrorResponse"}}}
    responses["409"]["content"] = {"application/json": {"schema": {"$ref": "#/components/schemas/ConflictErrorResponse"}}}
    responses["422"]["content"] = {"application/json": {"schema": {"$ref": ADMIN_VALIDATION_ERROR_REF}}}


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
            _apply_error_responses(path, operation)

    app.openapi_schema = schema
    return app.openapi_schema
