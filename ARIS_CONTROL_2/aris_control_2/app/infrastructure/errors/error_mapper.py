from aris_control_2.clients.aris3_client_sdk.http_client import APIError


class ErrorMapper:
    _KNOWN_CODES = {
        "PERMISSION_DENIED": ("Permiso denegado para la operación solicitada.", "Solicita permisos al administrador."),
        "TENANT_CONTEXT_REQUIRED": ("Selecciona un tenant para continuar.", "Elige un tenant en la opción 'Select tenant'."),
        "TENANT_SCOPE_REQUIRED": ("La operación requiere contexto de tenant.", "Inicia sesión nuevamente con un usuario tenant-scoped."),
        "TENANT_STORE_MISMATCH": ("La tienda elegida no pertenece al tenant efectivo.", "Selecciona una tienda válida para el tenant activo."),
        "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD": (
            "La clave de idempotencia ya fue usada con otro payload.",
            "Regenera el intento antes de reintentar.",
        ),
        "IDEMPOTENT_REPLAY": ("Operación ya procesada previamente.", "Verifica el estado final antes de reenviar."),
        "INTERNAL_ERROR": ("Error interno/transitorio en la operación.", "Reintenta en unos segundos."),
        "VALIDATION_ERROR": ("Error de validación en la solicitud.", "Revisa los campos obligatorios y formato."),
        "TIMEOUT_ERROR": ("El servidor tardó demasiado en responder.", "Pulsa 'Reintentar' para usar la misma operación."),
        "NETWORK_ERROR": ("No hay conectividad hacia el API.", "Verifica red/VPN y vuelve a intentar."),
    }

    _STATUS_HINTS = {
        403: ("PERMISSION_DENIED", "Permiso denegado para la operación solicitada.", "Solicita permisos al administrador."),
        409: ("IDEMPOTENCY_CONFLICT", "Conflicto de idempotencia detectado.", "Usa Reintentar o valida el resultado previo."),
        422: ("VALIDATION_ERROR", "Error de validación en la solicitud.", "Revisa campos y formato enviados."),
        500: ("INTERNAL_ERROR", "Error interno en el servicio.", "Reintenta y comparte el trace_id si persiste."),
    }

    @classmethod
    def to_payload(cls, error: Exception) -> dict:
        if isinstance(error, APIError):
            status_code = error.status_code or -1
            mapped = cls._STATUS_HINTS.get(status_code)
            if mapped is None and status_code >= 500:
                mapped = cls._STATUS_HINTS[500]
            if mapped is not None:
                code, message, suggestion = mapped
            else:
                message, suggestion = cls._KNOWN_CODES.get(
                    error.code,
                    (error.message, "Contacta soporte con el trace_id."),
                )
                code = error.code
            return {
                "code": code,
                "message": message,
                "details": error.details,
                "trace_id": error.trace_id,
                "suggestion": suggestion,
            }
        return {
            "code": "INTERNAL_ERROR",
            "message": str(error),
            "details": None,
            "trace_id": None,
            "suggestion": "Reintenta y, si persiste, reporta el incidente.",
        }

    @classmethod
    def to_display_message(cls, error: Exception) -> str:
        payload = cls.to_payload(error)
        return f"[{payload['code']}] {payload['message']} (trace_id={payload['trace_id']})"
