from aris_control_2.clients.aris3_client_sdk.http_client import APIError


class ErrorMapper:
    _KNOWN_CODES = {
        "PERMISSION_DENIED": "Permiso denegado para la operación solicitada.",
        "TENANT_CONTEXT_REQUIRED": "Selecciona un tenant para continuar.",
        "TENANT_SCOPE_REQUIRED": "La operación requiere contexto de tenant.",
        "TENANT_STORE_MISMATCH": "La tienda no pertenece al tenant seleccionado.",
        "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD": "La clave de idempotencia ya fue usada con otro payload.",
    }

    @classmethod
    def to_display_message(cls, error: Exception) -> str:
        if isinstance(error, APIError):
            mapped = cls._KNOWN_CODES.get(error.code, error.message)
            return f"[{error.code}] {mapped} (trace_id={error.trace_id})"
        return str(error)
