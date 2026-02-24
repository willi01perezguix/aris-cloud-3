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
        "description": "Administrative access-control management (role templates, tenant/store overlays, user overrides). Scope is resolved from JWT/context when not explicit.",
    },
    {"name": "Admin Settings", "description": "Administrative runtime settings endpoints."},
    {
        "name": "Access Control Scoped",
        "description": "Scope-explicit access-control endpoints where tenant/store/user identifiers are provided in path parameters.",
    },
]

_STATUS_CANONICAL_DESCRIPTION = (
    "Canonical values are uppercase (`ACTIVE`, `SUSPENDED`, `CANCELED`). "
    "Lowercase variants are accepted only for backward compatibility."
)


_ADMIN_DOC_OVERRIDES: dict[tuple[str, str], dict[str, str]] = {
    ("/aris3/admin/tenants", "get"): {
        "summary": "List tenants",
        "description": "Lists tenants with optional filters and pagination for platform administration.",
    },
    ("/aris3/admin/tenants", "post"): {
        "summary": "Create tenant",
        "description": "Creates a tenant record. Requires idempotency key and superadmin scope.",
    },
    ("/aris3/admin/tenants/{tenant_id}", "get"): {
        "summary": "Get tenant",
        "description": "Retrieves one tenant by identifier.",
    },
    ("/aris3/admin/tenants/{tenant_id}", "patch"): {
        "summary": "Update tenant",
        "description": "Partially updates tenant fields.",
    },
    ("/aris3/admin/stores", "get"): {
        "summary": "List stores",
        "description": "Lists stores with tenant-aware filters, pagination, and sorting.",
    },
    ("/aris3/admin/stores", "post"): {
        "summary": "Create store",
        "description": (
            "Creates a store under an explicit tenant scope.\n\n"
            "- **Canonical input**: send `tenant_id` in the JSON body.\n"
            "- **Legacy compatibility**: optional `query_tenant_id` is supported only for backward compatibility.\n"
            "- **Consistency rule**: when both values are sent, `tenant_id` and `query_tenant_id` must match.\n"
            "- **Admin rule**: `SUPERADMIN` and `PLATFORM_ADMIN` must provide an explicit tenant (no implicit fallback)."
        ),
    },
    ("/aris3/admin/stores/{store_id}", "get"): {
        "summary": "Get store",
        "description": "Retrieves one store by identifier within tenant scope.",
    },
    ("/aris3/admin/stores/{store_id}", "patch"): {
        "summary": "Update store",
        "description": "Partially updates store fields.",
    },
    ("/aris3/admin/stores/{store_id}", "delete"): {
        "summary": "Delete store",
        "description": "Deletes a store after dependency safeguards are validated.",
    },
    ("/aris3/admin/users", "get"): {
        "summary": "List users",
        "description": "Lists users for the current tenant scope with optional filters and pagination.",
    },
    ("/aris3/admin/users", "post"): {
        "summary": "Create user",
        "description": (
            "Creates a user in tenant scope with role/store validations.\n\n"
            "- **Canonical input**: send `store_id` in the JSON body.\n"
            "- **Tenant resolution**: backend derives `tenant_id` from `store.tenant_id`.\n"
            "- **Deprecated field**: body `tenant_id` is optional and validated only for payload consistency."
        ),
    },
    ("/aris3/admin/users/{user_id}", "get"): {
        "summary": "Get user",
        "description": "Retrieves one user by identifier within tenant scope.",
    },
    ("/aris3/admin/users/{user_id}", "patch"): {
        "summary": "Update user",
        "description": "Partially updates user profile fields.",
    },
    ("/aris3/admin/users/{user_id}", "delete"): {
        "summary": "Delete user",
        "description": "Deletes a user after dependency safeguards are validated.",
    },
    ("/aris3/admin/tenants/{tenant_id}", "delete"): {
        "summary": "Delete tenant",
        "description": "Deletes a tenant after dependency safeguards are validated.",
    },
    ("/aris3/admin/settings/return-policy", "get"): {
        "summary": "Get return policy settings",
        "description": "Returns current return-policy configuration for the resolved admin tenant scope.",
    },
    ("/aris3/admin/settings/return-policy", "patch"): {
        "summary": "Patch return policy settings",
        "description": "Partially updates return-policy configuration; omitted fields remain unchanged.",
    },
    ("/aris3/admin/settings/variant-fields", "get"): {
        "summary": "Get variant field labels",
        "description": (
            "Returns current variant-field labels. Tenant admins use JWT/context scope; "
            "superadmin must pass `tenant_id` query param."
        ),
    },
    ("/aris3/admin/settings/variant-fields", "patch"): {
        "summary": "Patch variant field labels",
        "description": (
            "Partially updates variant-field labels; omitted fields remain unchanged. "
            "Tenant admins use JWT/context scope; superadmin must pass `tenant_id` query param."
        ),
    },
    ("/aris3/admin/access-control/effective-permissions", "get"): {
        "summary": "Resolve effective permissions (admin)",
        "description": (
            "Admin endpoint for effective permission resolution for a target user.\n\n"
            "- Scope defaults to JWT/context when not explicitly provided.\n"
            "- Permission hierarchy: 1) Role Template, 2) Tenant/Store overlays (allow/deny), 3) User overrides, 4) Effective permissions.\n"
            "- Response includes canonical `subject`, resolved `permissions`, `denies_applied`, `sources_trace`, and `trace_id`."
        ),
    },
    ("/aris3/access-control/permission-catalog", "get"): {
        "summary": "Permission catalog",
        "description": (
            "Scoped permission catalog resolved from authenticated context and optional query parameters. "
            "Lists permission keys available for role templates, overlays, and user overrides."
        ),
    },
    ("/aris3/access-control/effective-permissions", "get"): {
        "summary": "Resolve effective permissions (current context)",
        "description": "Computes effective permissions for the authenticated request context.",
    },
}


_ACCESS_CONTROL_SUMMARY_OVERRIDES: dict[tuple[str, str], str] = {
    ("/aris3/access-control/tenants/{tenant_id}/stores/{store_id}/users/{user_id}/effective-permissions", "get"): "Effective permissions for store user",
    ("/aris3/access-control/tenants/{tenant_id}/role-policies/{role_name}", "get"): "Get tenant role policy",
    ("/aris3/access-control/tenants/{tenant_id}/stores/{store_id}/role-policies/{role_name}", "get"): "Get store role policy",
    ("/aris3/access-control/tenants/{tenant_id}/users/{user_id}/permission-overrides", "get"): "Get user permission overrides",
    ("/aris3/access-control/platform/role-policies/{role_name}", "get"): "Get platform role policy",
    ("/aris3/access-control/tenants/{tenant_id}/role-policies/{role_name}", "put"): "Replace tenant role policy",
    ("/aris3/access-control/tenants/{tenant_id}/stores/{store_id}/role-policies/{role_name}", "put"): "Replace store role policy",
    ("/aris3/access-control/tenants/{tenant_id}/users/{user_id}/permission-overrides", "put"): "Replace user permission overrides",
    ("/aris3/access-control/platform/role-policies/{role_name}", "put"): "Replace platform role policy",
    ("/aris3/admin/access-control/role-templates/{role_name}", "put"): "Replace admin role template",
    ("/aris3/admin/access-control/user-overrides/{user_id}", "patch"): "Patch user overrides (admin)",
}


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
            context = "Scoped endpoint with explicit tenant/store/user identifiers in the request path."
        else:
            if method == "get":
                context = "Scoped endpoint resolved from authenticated context and optional query parameters."
            else:
                context = "Scoped endpoint resolved from authenticated context and optional request body/query parameters."
        operation["description"] = f"{context}\n\n{hierarchy}"

    if path.startswith("/aris3/admin/access-control"):
        operation["description"] = (
            "Admin endpoint: tenant/store/user scope is resolved from JWT/context unless explicit path/query/body parameters override it."
            f"\n\n{hierarchy}"
        )

    if path == "/aris3/admin/access-control/permission-catalog":
        operation.pop("deprecated", None)
        operation["summary"] = "Admin permission catalog"
        operation["description"] = (
            "Admin permission catalog for role templates, tenant/store overlays, and user overrides."
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

    explicit_identifier_path = any(token in path for token in ("{tenant_id}", "{store_id}", "{user_id}"))
    should_include_404 = (method in {"get", "put", "patch", "delete"} and explicit_identifier_path) or (
        path in {"/aris3/admin/users", "/aris3/admin/stores"} and method == "post"
    )
    if should_include_404:
        responses.setdefault("404", {"description": _not_found_description(path)})

    if method in {"post", "put", "patch", "delete"}:
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


def _polish_admin_store_create_parameters(path: str, method: str, operation: dict) -> None:
    if not (path == "/aris3/admin/stores" and method == "post"):
        return

    deduped_parameters: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for parameter in operation.get("parameters", []):
        key = (parameter.get("in") or "", parameter.get("name") or "")
        if key in seen:
            continue
        seen.add(key)
        deduped_parameters.append(parameter)

    operation["parameters"] = [
        parameter
        for parameter in deduped_parameters
        if not (parameter.get("in") == "query" and parameter.get("name") == "tenant_id")
    ]

    for parameter in operation.get("parameters", []):
        if parameter.get("in") == "query" and parameter.get("name") == "query_tenant_id":
            parameter["deprecated"] = True
            parameter["description"] = (
                "Legacy tenant selector kept for backward compatibility. "
                "Prefer body.tenant_id as canonical source."
            )
            schema = parameter.setdefault("schema", {})
            schema["description"] = parameter["description"]

    body_content = operation.get("requestBody", {}).get("content", {}).get("application/json", {})
    if body_content:
        body_content.setdefault(
            "examples",
            {
                "canonical_body_tenant": {
                    "summary": "Recommended (canonical)",
                    "value": {"name": "Store Centro", "tenant_id": "4f7f2c5e-9cfd-4efa-a575-2a0ad38df4e8"},
                },
                "legacy_query_tenant": {
                    "summary": "Legacy compatibility (query_tenant_id)",
                    "description": "Prefer sending tenant_id in request body for new integrations.",
                    "value": {"name": "Store Centro"},
                },
            },
        )


def _polish_admin_and_access_control_descriptions(path: str, method: str, operation: dict) -> None:
    override = _ADMIN_DOC_OVERRIDES.get((path, method))
    if override:
        operation.update(override)

    if path == "/aris3/admin/tenants/{tenant_id}/actions" and method == "post":
        operation["summary"] = "Execute tenant admin action"
        operation["description"] = (
            "Executes a tenant action. Currently supported action: `set_status` (requires `status`).\n\n"
            f"{_STATUS_CANONICAL_DESCRIPTION}"
        )

    if path == "/aris3/admin/users/{user_id}/actions" and method == "post":
        operation["summary"] = "Execute user admin action"
        operation["description"] = (
            "Dispatches one admin action over a user.\n\n"
            "- `action=set_status`: requires `status`.\n"
            "- `action=set_role`: requires `role`.\n"
            "- `action=reset_password`: optional `temporary_password`; if omitted, server generates one.\n"
            "- `transaction_id` is required for idempotency/audit correlation.\n\n"
            f"{_STATUS_CANONICAL_DESCRIPTION}"
        )

    if path in {"/aris3/admin/tenants", "/aris3/admin/stores", "/aris3/admin/users"}:
        description = operation.get("description") or ""
        operation["description"] = description.strip()

    if path == "/aris3/admin/users" and method == "get":
        cleaned_parameters: list[dict] = []
        for parameter in operation.get("parameters", []):
            if parameter.get("name") == "--":
                continue
            description = parameter.get("description")
            if not description:
                cleaned_parameters.append(parameter)
                continue
            cleaned_description = description.replace("--", "").strip()
            if cleaned_description:
                parameter["description"] = cleaned_description
                cleaned_parameters.append(parameter)
        operation["parameters"] = cleaned_parameters

    summary_override = _ACCESS_CONTROL_SUMMARY_OVERRIDES.get((path, method))
    if summary_override:
        operation["summary"] = summary_override


def _polish_status_schema_descriptions(schema: dict) -> None:
    components = schema.get("components", {}).get("schemas", {})
    for schema_name in (
        "TenantItem",
        "UserItem",
        "TenantActionRequest",
        "UserActionRequest",
        "SetUserStatusActionRequest",
    ):
        status_prop = components.get(schema_name, {}).get("properties", {}).get("status")
        if status_prop is None:
            continue
        existing = (status_prop.get("description") or "").strip()
        status_prop["description"] = f"{existing} {_STATUS_CANONICAL_DESCRIPTION}".strip()


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
            _polish_admin_store_create_parameters(path, method, operation)
            _polish_admin_and_access_control_descriptions(path, method, operation)

    _polish_status_schema_descriptions(schema)

    app.openapi_schema = schema
    return app.openapi_schema
