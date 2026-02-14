from aris_control_2.clients.aris3_client_sdk.http_client import APIError


class ErrorMapper:
    _KNOWN_CODES = {
        "PERMISSION_DENIED": "Permiso denegado para la operación solicitada.",
        "TENANT_CONTEXT_REQUIRED": "Selecciona un tenant para continuar.",
        "TENANT_SCOPE_REQUIRED": "La operación requiere contexto de tenant.",
        "TENANT_STORE_MISMATCH": "La tienda elegida no pertenece al tenant efectivo.",
        "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD": "La clave de idempotencia ya fue usada con otro payload.",
    }

    @classmethod
    def to_payload(cls, error: Exception) -> dict:
        if isinstance(error, APIError):
            return {
                "code": error.code,
                "message": cls._KNOWN_CODES.get(error.code, error.message),
                "details": error.details,
                "trace_id": error.trace_id,
            }
        return {"code": "UNEXPECTED", "message": str(error), "details": None, "trace_id": None}

    @classmethod
    def to_display_message(cls, error: Exception) -> str:
        payload = cls.to_payload(error)
        return f"[{payload['code']}] {payload['message']} (trace_id={payload['trace_id']})"
