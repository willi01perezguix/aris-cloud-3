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
        "name": "Access Control (Self)",
        "description": "Self-service access-control read endpoints resolved from the authenticated request context.",
    },
    {"name": "pos-sales", "description": "Point-of-sale sales issuance, listing, detail, and action workflows."},
    {"name": "pos-returns", "description": "Point-of-sale return eligibility, quote, creation, and return action workflows."},
    {"name": "pos-cash", "description": "Point-of-sale cash sessions, movements, reconciliation, day close, and cash cut workflows."},
    {"name": "pos-drawer", "description": "Point-of-sale drawer events and lifecycle endpoints."},
    {"name": "pos-advances", "description": "Point-of-sale customer advances issuance, lookup, alerts, detail, and action workflows."},
    {"name": "stock", "description": "Inventory stock operations endpoints."},
    {"name": "transfers", "description": "Inventory transfer create/list/detail and action workflows."},
    {"name": "reports", "description": "Business reporting endpoints."},
    {"name": "exports", "description": "Report export generation and download endpoints."},
    {"name": "assets", "description": "Assets and image management endpoints."},
    {"name": "users", "description": "User self-context endpoints."},
    {"name": "auth", "description": "Authentication and token endpoints."},
    {"name": "ops", "description": "Operational endpoints for platform monitoring."},
]

_STATUS_CANONICAL_DESCRIPTION = (
    "Canonical values are uppercase (`ACTIVE`, `SUSPENDED`, `CANCELED`)."
)


_ADMIN_DOC_OVERRIDES: dict[tuple[str, str], dict[str, str]] = {
    ("/aris3/auth/login", "post"): {
        "summary": "Login",
        "description": "Canonical authentication endpoint for product/API clients using JSON payloads.",
    },
    ("/aris3/auth/token", "post"): {
        "summary": "OAuth2 token helper (Swagger/tooling compatibility)",
        "description": (
            "Compatibility endpoint for OAuth2 Password Flow tooling (for example Swagger Authorize). "
            "Use canonical `POST /aris3/auth/login` for product/client integrations."
        ),
    },
    ("/aris3/auth/change-password", "patch"): {
        "summary": "Change password",
        "description": "Canonical authenticated password change endpoint (`PATCH /aris3/auth/change-password`).",
    },
    ("/aris3/auth/change-password", "post"): {
        "summary": "Change password (deprecated alias)",
        "description": "Deprecated compatibility alias; use canonical `PATCH /aris3/auth/change-password`.",
    },
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
            "- **backward compatibility**: deprecated `query_tenant_id` is accepted as legacy alias and must match body `tenant_id` when both are provided.\n"
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
        "description": "Safe delete: blocks when dependencies exist. Use `POST /aris3/admin/stores/{store_id}/purge` for destructive cleanup.",
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
            "- **Tenant resolution**: backend derives tenant scope from `store.tenant_id`."
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
        "description": "Safe delete: blocks when dependencies exist. Use `POST /aris3/admin/users/{user_id}/purge` for destructive cleanup.",
    },
    ("/aris3/admin/tenants/{tenant_id}", "delete"): {
        "summary": "Delete tenant",
        "description": "Safe delete: blocks when dependencies exist. Use `POST /aris3/admin/tenants/{tenant_id}/purge` for destructive cleanup.",
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
            "Administrative/internal settings endpoint for variant-field labels. Tenant admins use JWT/context scope; "
            "superadmin must pass `tenant_id` query param."
        ),
    },
    ("/aris3/admin/settings/variant-fields", "patch"): {
        "summary": "Patch variant field labels",
        "description": (
            "Administrative/internal settings endpoint that partially updates variant-field labels; omitted fields remain unchanged. "
            "Tenant admins use JWT/context scope; superadmin must pass `tenant_id` query param."
        ),
    },
    ("/aris3/stock/actions", "post"): {
        "summary": "Execute stock action (operations workflow)",
        "description": (
            "Operational stock mutation endpoint for inventory workflows. "
            "Not intended as a generic public catalog/product-discovery endpoint."
        ),
    },
    ("/aris3/ops/metrics", "get"): {
        "summary": "Operations metrics (internal)",
        "description": "Operational Prometheus metrics endpoint for infrastructure/observability tooling. Not a product workflow endpoint.",
    },
    ("/aris3/admin/access-control/effective-permissions", "get"): {
        "summary": "Resolve effective permissions (admin)",
        "description": (
            "Administrative/internal access-control endpoint for effective permission resolution for a target user.\n\n"
            "- Scope defaults to JWT/context when not explicitly provided.\n"
            "- Permission hierarchy: 1) Role Template, 2) Tenant/Store overlays (allow/deny), 3) User overrides, 4) Effective permissions.\n"
            "- Response includes canonical `subject`, resolved `permissions`, `denies_applied`, `sources_trace`, and `trace_id`."
        ),
    },
    ("/aris3/access-control/permission-catalog", "get"): {
        "summary": "Permission catalog",
        "description": (
            "Self-context permission catalog resolved from authenticated context. "
            "Lists permission keys available for role templates, overlays, and user overrides."
        ),
    },
    ("/aris3/access-control/effective-permissions", "get"): {
        "summary": "Resolve effective permissions (current context)",
        "description": "Computes effective permissions for the authenticated request context.",
    },
}


_ACCESS_CONTROL_SUMMARY_OVERRIDES: dict[tuple[str, str], str] = {
    ("/aris3/admin/access-control/role-templates/{role_name}", "put"): "Replace admin role template",
    ("/aris3/admin/access-control/user-overrides/{user_id}", "patch"): "Patch user overrides (admin)",
}


_ERROR_PROPS = {
    "code": {"type": "string"},
    "message": {"type": "string"},
    "details": {
        "anyOf": [
            {"type": "object", "additionalProperties": True},
            {"type": "array", "items": {}},
            {"type": "string"},
            {"type": "null"},
        ]
    },
    "trace_id": {"type": "string", "example": "trace-123"},
}

_ERROR_CODE_DESCRIPTION = (
    "Machine-readable error code. Canonical vocabulary for new clients: "
    "`INVALID_TOKEN`, `PERMISSION_DENIED`, `RESOURCE_NOT_FOUND`, `CONFLICT`, `VALIDATION_ERROR`. "
    "OpenAPI examples and shared schemas use canonical values for consistency. "
    "Compatibility aliases may still appear in legacy/public POS responses "
    "(`UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `BUSINESS_CONFLICT`)."
)

_ERROR_CODE_CANONICAL_ALIASES = {
    "UNAUTHORIZED": "INVALID_TOKEN",
    "FORBIDDEN": "PERMISSION_DENIED",
    "NOT_FOUND": "RESOURCE_NOT_FOUND",
    "BUSINESS_CONFLICT": "CONFLICT",
}

ERROR_RESPONSE_SCHEMAS = {
    "ApiError": {
        "type": "object",
        "required": ["code", "message", "details", "trace_id"],
        "properties": {
            **_ERROR_PROPS,
            "code": {
                "type": "string",
                "description": _ERROR_CODE_DESCRIPTION,
                "example": "RESOURCE_NOT_FOUND",
            },
            "message": {"type": "string", "example": "Resource not found"},
        },
    },
    "ErrorResponse": {"$ref": "#/components/schemas/ApiError"},
    "NotFoundError": {
        "type": "object",
        "required": ["code", "message"],
        "properties": {
            **_ERROR_PROPS,
            "code": {"type": "string", "example": "RESOURCE_NOT_FOUND"},
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
            "code": {"type": "string", "example": "RESOURCE_NOT_FOUND"},
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
    "BusinessErrorResponse": {"$ref": "#/components/schemas/ConflictErrorResponse"},
    "ValidationErrorResponse": {"$ref": "#/components/schemas/ValidationError"},
}

ERROR_RESPONSES = {
    "UnauthorizedError": {
        "description": "Unauthorized. Returned when the bearer token is missing, invalid, or expired.",
        "headers": {
            "WWW-Authenticate": {
                "description": "Bearer authentication challenge header.",
                "schema": {"type": "string"},
                "example": "Bearer",
            }
        },
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ApiError"},
                "example": {
                    "code": "INVALID_TOKEN",
                    "message": "Invalid token",
                    "details": None,
                    "trace_id": "trace-123",
                },
            }
        },
    },
    "ForbiddenError": {
        "description": "Forbidden. Returned when the token is valid but lacks required permissions.",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ApiError"},
                "example": {
                    "code": "PERMISSION_DENIED",
                    "message": "Permission denied",
                    "details": None,
                    "trace_id": "trace-123",
                },
            }
        },
    },
    "UnauthorizedError401": {"$ref": "#/components/responses/UnauthorizedError"},
    "ForbiddenError403": {"$ref": "#/components/responses/ForbiddenError"},
}




IDEMPOTENCY_KEY_PARAMETER = {
    "name": "Idempotency-Key",
    "in": "header",
    "required": True,
    "description": "Idempotency key required for mutating admin operations.",
    "schema": {"type": "string"},
}

PUBLIC_ENDPOINTS_WITHOUT_AUTH_ERRORS = {
    "/health",
    "/ready",
    "/aris3/auth/login",
    "/aris3/auth/token",
}

AUTH_ENDPOINTS_WITH_VALIDATION = {
    "/aris3/auth/login",
    "/aris3/auth/change-password",
    "/aris3/auth/token",
}


def _operation_id(method: str, path: str) -> str:
    normalized = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    return f"{method}_{normalized}"


def _assign_tag(path: str) -> str | None:
    if path.startswith("/aris3/access-control"):
        return "Access Control (Self)"
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
        if method == "get":
            context = "Self-context endpoint resolved from the authenticated request context."
        else:
            context = "Self-context endpoint resolved from the authenticated request context."
        operation["description"] = f"{context}\n\n{hierarchy}"

    if path.startswith("/aris3/admin/access-control"):
        operation["description"] = (
            "Administrative/internal access-control endpoint: tenant/store/user scope is resolved from JWT/context unless explicit path/query/body parameters override it."
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
    if path in AUTH_ENDPOINTS_WITH_VALIDATION and method in {"post", "patch"}:
        responses = operation.setdefault("responses", {})
        responses["422"] = {
            "description": "Validation error",
            "content": {"application/json": {"schema": {"$ref": VALIDATION_ERROR_REF}}},
        }

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
                "example": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": not_found_message,
                    "details": {"path": path, "reason": "resource does not exist"},
                    "trace_id": "trace-123",
                },
            }
        }

    if "409" in responses:
        responses["409"]["description"] = "Resource conflict"
        responses["409"]["content"] = {
            "application/json": {
                "schema": {"$ref": CONFLICT_ERROR_REF},
                "example": {
                    "code": "CONFLICT",
                    "message": "Resource conflict",
                    "details": {"reason": "business validation conflict"},
                    "trace_id": "trace-123",
                },
            }
        }


def _apply_auth_error_references(path: str, operation: dict) -> None:
    if path in PUBLIC_ENDPOINTS_WITHOUT_AUTH_ERRORS:
        return

    security = operation.get("security") or []
    if not security:
        return

    responses = operation.setdefault("responses", {})
    responses.setdefault("401", {"$ref": "#/components/responses/UnauthorizedError"})
    responses.setdefault("403", {"$ref": "#/components/responses/ForbiddenError"})


def _apply_idempotency_header(path: str, method: str, operation: dict) -> None:
    if not path.startswith("/aris3/admin/"):
        return
    if method not in {"post", "put", "patch", "delete"}:
        return
    parameters = operation.setdefault("parameters", [])
    if not any((p.get("in") == "header" and p.get("name") == "Idempotency-Key") for p in parameters):
        parameters.append(deepcopy(IDEMPOTENCY_KEY_PARAMETER))


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

    body_content = operation.get("requestBody", {}).get("content", {}).get("application/json", {})
    if body_content:
        body_content.setdefault(
            "examples",
            {
                "canonical_body_tenant": {
                    "summary": "Recommended (canonical)",
                    "value": {"name": "Store Centro", "tenant_id": "4f7f2c5e-9cfd-4efa-a575-2a0ad38df4e8"},
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


def _polish_reports_exports_contract(path: str, method: str, operation: dict) -> None:
    if path == "/aris3/exports/{export_id}/download" and method == "get":
        responses = operation.setdefault("responses", {})
        response_200 = responses.get("200", {})
        content = response_200.get("content", {})
        content.pop("application/json", None)
        for media_type in (
            "text/csv",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/octet-stream",
        ):
            content.setdefault(media_type, {}).setdefault("schema", {"type": "string", "format": "binary"})


def _polish_exports_schema_descriptions(schema: dict) -> None:
    components = schema.get("components", {}).get("schemas", {})
    source_type_schema = components.get("ExportSourceType")
    if source_type_schema:
        source_type_schema["description"] = (
            "Supported report sources for exports: reports_overview, reports_daily, reports_calendar."
        )

    format_schema = components.get("ExportFormat")
    if format_schema:
        format_schema["description"] = "Supported export file formats: csv, xlsx, pdf."

    status_schema = components.get("ExportStatus")
    if status_schema:
        status_schema["description"] = (
            "Export lifecycle states: CREATED (accepted/pending generation), "
            "READY (generated and downloadable), FAILED (generation failed)."
        )


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




def _prune_public_legacy_contract(schema: dict) -> None:
    components = schema.get("components", {}).get("schemas", {})

    for schema_name, field_names in {
        "SaleLineBySkuInput": {"unit_price", "status", "location_code", "pool", "snapshot"},
        "SaleLineByEpcInput": {"unit_price", "status", "location_code", "pool", "snapshot"},
        "ReturnQuoteRequest": {"tenant_id"},
        "CompleteReturnActionRequest": {"tenant_id"},
        "VoidReturnActionRequest": {"tenant_id"},
        "OpenCashSessionRequest": {"tenant_id"},
        "CashInRequest": {"tenant_id"},
        "CashOutRequest": {"tenant_id"},
        "CloseCashSessionRequest": {"tenant_id"},
        "PosCashDayCloseActionRequest": {"tenant_id"},
        "PosCashCutQuoteRequest": {"tenant_id"},
        "PosCashCutCreateRequest": {"tenant_id"},
        "PosCashCutActionRequest": {"tenant_id"},
        "UserCreateRequest": {"tenant_id"},
    }.items():
        model = components.get(schema_name, {})
        props = model.get("properties", {})
        required = model.get("required", [])
        for field in field_names:
            props.pop(field, None)
            if field in required:
                required.remove(field)

    for path in (
        "/aris3/pos/cash/session/current",
        "/aris3/pos/cash/movements",
        "/aris3/pos/cash/day-close/summary",
        "/aris3/pos/cash/reconciliation/breakdown",
        "/aris3/pos/cash/cuts",
        "/aris3/pos/cash/cuts/{cut_id}",
    ):
        op = schema.get("paths", {}).get(path, {}).get("get", {})
        if op:
            op["parameters"] = [
                p for p in op.get("parameters", []) if p.get("name") != "tenant_id"
            ]

def _enforce_public_request_contracts(schema: dict) -> None:
    components = schema.get("components", {}).get("schemas", {})

    for schema_name, field_names in {
        "TransferCreateRequest": {"tenant_id"},
        "TransferUpdateRequest": {"tenant_id"},
        "TransferActionRequest": {"tenant_id"},
    }.items():
        model = components.get(schema_name, {})
        props = model.get("properties", {})
        required = model.get("required", [])
        for field in field_names:
            props.pop(field, None)
            if field in required:
                required.remove(field)

    for model in components.values():
        if not isinstance(model, dict):
            continue
        required = model.get("required", [])
        if "transaction_id" not in required:
            continue
        prop = model.get("properties", {}).get("transaction_id")
        if not isinstance(prop, dict):
            continue
        if "anyOf" in prop:
            non_null = [entry for entry in prop["anyOf"] if entry.get("type") != "null"]
            if len(non_null) == 1:
                title = prop.get("title")
                description = prop.get("description")
                examples = prop.get("examples")
                default = prop.get("default")
                prop.clear()
                prop.update(non_null[0])
                if title:
                    prop["title"] = title
                if description:
                    prop["description"] = description
                if examples:
                    prop["examples"] = examples
                if default is not None:
                    prop["default"] = default
        prop.pop("nullable", None)


def _set_endpoint_error_examples(schema: dict) -> None:
    paths = schema.get("paths", {})

    endpoint_examples: dict[tuple[str, str, str], dict] = {
        ("/aris3/pos/returns", "get", "409"): {
            "code": "BUSINESS_CONFLICT",
            "message": "Return list cannot be generated for current filters",
            "details": {"reason": "business rule conflict"},
            "trace_id": "trace-returns-list-409",
        },
        ("/aris3/pos/returns/eligibility", "get", "409"): {
            "code": "BUSINESS_CONFLICT",
            "message": "Eligibility cannot be resolved for the provided sale",
            "details": {"reason": "sale state is not return-eligible"},
            "trace_id": "trace-returns-eligibility-409",
        },
        ("/aris3/pos/returns/quote", "post", "401"): {"code": "INVALID_TOKEN", "message": "Authentication required", "details": None, "trace_id": "trace-returns-quote-401"},
        ("/aris3/pos/returns/quote", "post", "403"): {"code": "PERMISSION_DENIED", "message": "Permission denied", "details": {"required_permission": "POS_RETURN_MANAGE"}, "trace_id": "trace-returns-quote-403"},
        ("/aris3/pos/returns/quote", "post", "404"): {"code": "RESOURCE_NOT_FOUND", "message": "Resource not found", "details": {"resource": "sale"}, "trace_id": "trace-returns-quote-404"},
        ("/aris3/pos/returns/quote", "post", "409"): {"code": "BUSINESS_CONFLICT", "message": "Quote cannot be computed", "details": {"reason": "business rule conflict"}, "trace_id": "trace-returns-quote-409"},
        ("/aris3/pos/returns/{return_id}/actions", "post", "401"): {"code": "INVALID_TOKEN", "message": "Authentication required", "details": None, "trace_id": "trace-returns-actions-401"},
        ("/aris3/pos/returns/{return_id}/actions", "post", "403"): {"code": "PERMISSION_DENIED", "message": "Permission denied", "details": {"required_permission": "POS_RETURN_MANAGE"}, "trace_id": "trace-returns-actions-403"},
        ("/aris3/pos/returns/{return_id}/actions", "post", "404"): {"code": "RESOURCE_NOT_FOUND", "message": "Return not found", "details": {"resource": "return"}, "trace_id": "trace-returns-actions-404"},
        ("/aris3/pos/returns/{return_id}/actions", "post", "409"): {"code": "BUSINESS_CONFLICT", "message": "Action cannot be executed for current return state", "details": {"reason": "state transition not allowed"}, "trace_id": "trace-returns-actions-409"},
        ("/aris3/pos/returns/{return_id}", "get", "422"): {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "return_id", "message": "Invalid identifier format", "type": "value_error"}]}, "trace_id": "trace-returns-detail-422"},
        ("/aris3/pos/cash/session/current", "get", "409"): {"code": "BUSINESS_CONFLICT", "message": "Current cash session cannot be resolved", "details": {"reason": "multiple open sessions detected"}, "trace_id": "trace-cash-current-409"},
        ("/aris3/pos/cash/session/current", "get", "422"): {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "store_id", "message": "store_id is required for this role", "type": "value_error"}]}, "trace_id": "trace-cash-current-422"},
        ("/aris3/pos/cash/movements", "get", "401"): {"code": "INVALID_TOKEN", "message": "Authentication required", "details": None, "trace_id": "trace-cash-movements-401"},
        ("/aris3/pos/cash/movements", "get", "403"): {"code": "PERMISSION_DENIED", "message": "Permission denied", "details": {"required_permission": "POS_CASH_VIEW"}, "trace_id": "trace-cash-movements-403"},
        ("/aris3/pos/cash/movements", "get", "409"): {"code": "BUSINESS_CONFLICT", "message": "Movements cannot be listed for current context", "details": {"reason": "cash day close in progress"}, "trace_id": "trace-cash-movements-409"},
        ("/aris3/pos/cash/movements", "get", "422"): {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "business_date_from", "message": "business_date_from must be <= business_date_to", "type": "value_error"}]}, "trace_id": "trace-cash-movements-422"},
        ("/aris3/pos/cash/day-close/actions", "post", "401"): {"code": "INVALID_TOKEN", "message": "Authentication required", "details": None, "trace_id": "trace-day-close-401"},
        ("/aris3/pos/cash/day-close/actions", "post", "403"): {"code": "PERMISSION_DENIED", "message": "Permission denied", "details": {"required_permission": "POS_CASH_MANAGE"}, "trace_id": "trace-day-close-403"},
        ("/aris3/pos/cash/day-close/actions", "post", "404"): {"code": "RESOURCE_NOT_FOUND", "message": "Resource not found", "details": {"resource": "cash_session"}, "trace_id": "trace-day-close-404"},
        ("/aris3/pos/cash/day-close/actions", "post", "409"): {"code": "BUSINESS_CONFLICT", "message": "Day close cannot be executed", "details": {"reason": "cash session is still open"}, "trace_id": "trace-day-close-409"},
        ("/aris3/pos/cash/day-close/summary", "get", "401"): {"code": "INVALID_TOKEN", "message": "Authentication required", "details": None, "trace_id": "trace-day-close-summary-401"},
        ("/aris3/pos/cash/day-close/summary", "get", "403"): {"code": "PERMISSION_DENIED", "message": "Permission denied", "details": {"required_permission": "POS_CASH_VIEW"}, "trace_id": "trace-day-close-summary-403"},
        ("/aris3/pos/cash/day-close/summary", "get", "409"): {"code": "BUSINESS_CONFLICT", "message": "Summary cannot be generated", "details": {"reason": "day close in inconsistent state"}, "trace_id": "trace-day-close-summary-409"},
        ("/aris3/pos/cash/day-close/summary", "get", "422"): {"code": "VALIDATION_ERROR", "message": "Validation error", "details": {"errors": [{"field": "business_date_from", "message": "business_date_from must be <= business_date_to", "type": "value_error"}]}, "trace_id": "trace-day-close-summary-422"},
        ("/aris3/pos/cash/reconciliation/breakdown", "get", "401"): {"code": "INVALID_TOKEN", "message": "Authentication required", "details": None, "trace_id": "trace-reconciliation-401"},
        ("/aris3/pos/cash/reconciliation/breakdown", "get", "403"): {"code": "PERMISSION_DENIED", "message": "Permission denied", "details": {"required_permission": "POS_CASH_VIEW"}, "trace_id": "trace-reconciliation-403"},
        ("/aris3/pos/cash/reconciliation/breakdown", "get", "404"): {"code": "RESOURCE_NOT_FOUND", "message": "Day close not found", "details": {"resource": "day_close"}, "trace_id": "trace-reconciliation-404"},
        ("/aris3/pos/cash/reconciliation/breakdown", "get", "409"): {"code": "BUSINESS_CONFLICT", "message": "Reconciliation cannot be computed", "details": {"reason": "cash session still open"}, "trace_id": "trace-reconciliation-409"},
        ("/aris3/pos/sales/{sale_id}/actions", "post", "409"): {
            "code": "BUSINESS_CONFLICT",
            "message": "Cannot checkout CASH payment without an open cash session",
            "details": {"action": "CHECKOUT", "payment_method": "CASH", "reason": "open cash session required"},
            "trace_id": "trace-sale-action-cash-409",
        },
    }

    for (path, method, status_code), example in endpoint_examples.items():
        operation = paths.get(path, {}).get(method, {})
        response = operation.get("responses", {}).get(status_code)
        if not response:
            continue
        media = response.setdefault("content", {}).setdefault("application/json", {})
        media.pop("examples", None)
        media["example"] = example


def _canonicalize_error_examples(schema: dict) -> None:
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for response in operation.get("responses", {}).values():
                if not isinstance(response, dict):
                    continue
                app_json = response.get("content", {}).get("application/json")
                if not isinstance(app_json, dict):
                    continue
                example = app_json.get("example")
                if isinstance(example, dict):
                    code = example.get("code")
                    if isinstance(code, str) and code in _ERROR_CODE_CANONICAL_ALIASES:
                        example["code"] = _ERROR_CODE_CANONICAL_ALIASES[code]

                examples = app_json.get("examples")
                if not isinstance(examples, dict):
                    continue
                for value in examples.values():
                    if not isinstance(value, dict):
                        continue
                    payload = value.get("value")
                    if not isinstance(payload, dict):
                        continue
                    code = payload.get("code")
                    if isinstance(code, str) and code in _ERROR_CODE_CANONICAL_ALIASES:
                        payload["code"] = _ERROR_CODE_CANONICAL_ALIASES[code]


def _normalize_admin_user_actions_request_schema(schema: dict) -> None:
    operation = schema.get("paths", {}).get("/aris3/admin/users/{user_id}/actions", {}).get("post", {})
    body_schema = (
        operation.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    if not isinstance(body_schema, dict):
        return

    clean_union = {
        "oneOf": [
            {
                "type": "object",
                "required": ["action", "status", "transaction_id"],
                "properties": {
                    "action": {"type": "string", "enum": ["set_status"]},
                    "status": {"type": "string", "enum": ["ACTIVE", "SUSPENDED", "CANCELED"]},
                    "transaction_id": {"type": "string"},
                },
            },
            {
                "type": "object",
                "required": ["action", "role", "transaction_id"],
                "properties": {
                    "action": {"type": "string", "enum": ["set_role"]},
                    "role": {"type": "string", "enum": ["USER", "MANAGER", "ADMIN"]},
                    "transaction_id": {"type": "string"},
                },
            },
            {
                "type": "object",
                "required": ["action", "transaction_id"],
                "properties": {
                    "action": {"type": "string", "enum": ["reset_password"]},
                    "temporary_password": {"type": "string"},
                    "transaction_id": {"type": "string"},
                },
            },
        ]
    }
    operation["requestBody"]["content"]["application/json"]["schema"] = clean_union


def _normalize_pos_action_discriminators(schema: dict) -> None:
    paths = schema.get("paths", {})
    components = schema.get("components", {}).get("schemas", {})
    action_paths = (
        ("/aris3/pos/sales/{sale_id}/actions", "post"),
        ("/aris3/pos/returns/{return_id}/actions", "post"),
        ("/aris3/pos/cash/session/actions", "post"),
    )
    for path, method in action_paths:
        operation = paths.get(path, {}).get(method, {})
        body_schema = (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
        discriminator = body_schema.get("discriminator", {})
        mapping = discriminator.get("mapping")
        if not isinstance(mapping, dict):
            continue

        normalized_mapping: dict[str, str] = {}
        for action, ref in mapping.items():
            if not isinstance(action, str):
                raise ValueError(f"Invalid discriminator action key for {method.upper()} {path}: {action}")
            canonical_action = action.upper()
            if not isinstance(ref, str) or not ref.startswith("#/components/schemas/"):
                raise ValueError(f"Invalid discriminator mapping ref for {method.upper()} {path}: {ref}")
            schema_name = ref.rsplit("/", 1)[-1]
            if schema_name not in components:
                raise ValueError(f"Missing discriminator schema `{schema_name}` for {method.upper()} {path}")
            existing_ref = normalized_mapping.get(canonical_action)
            if existing_ref and existing_ref != ref:
                raise ValueError(
                    f"Conflicting discriminator refs for action `{canonical_action}` on {method.upper()} {path}"
                )
            normalized_mapping[canonical_action] = ref

        discriminator["mapping"] = {key: normalized_mapping[key] for key in sorted(normalized_mapping)}


def harden_openapi_schema(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(title=app.title, version="1.0.0", routes=app.routes)
    schema["tags"] = TAG_METADATA
    components = schema.setdefault("components", {})
    component_schemas = components.setdefault("schemas", {})
    for name, schema_value in ERROR_RESPONSE_SCHEMAS.items():
        component_schemas[name] = deepcopy(schema_value)

    component_responses = components.setdefault("responses", {})
    for name, response_value in ERROR_RESPONSES.items():
        component_responses[name] = deepcopy(response_value)

    security_schemes = components.setdefault("securitySchemes", {})
    if "OAuth2PasswordBearer" in security_schemes:
        security_schemes["OAuth2PasswordBearer"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste JWT bearer token obtained from `/aris3/auth/login` or `/aris3/auth/token`.",
        }

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
            _apply_auth_error_references(path, operation)
            _apply_idempotency_header(path, method, operation)
            _polish_admin_store_create_parameters(path, method, operation)
            _polish_admin_and_access_control_descriptions(path, method, operation)
            _polish_reports_exports_contract(path, method, operation)

    _polish_status_schema_descriptions(schema)
    _polish_exports_schema_descriptions(schema)
    _prune_public_legacy_contract(schema)
    _enforce_public_request_contracts(schema)
    _set_endpoint_error_examples(schema)
    _canonicalize_error_examples(schema)
    _normalize_admin_user_actions_request_schema(schema)
    _normalize_pos_action_discriminators(schema)

    generated_schemas = schema.get("components", {}).get("schemas", {})
    generated_schemas.pop("HTTPValidationError", None)

    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            response_422 = operation.get("responses", {}).get("422", {})
            content = response_422.get("content", {}).get("application/json", {})
            schema_ref = content.get("schema", {}).get("$ref")
            if schema_ref == "#/components/schemas/HTTPValidationError":
                content["schema"] = {"$ref": VALIDATION_ERROR_REF}

    app.openapi_schema = schema
    return app.openapi_schema
