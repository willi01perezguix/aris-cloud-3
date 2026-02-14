from aris_control_2.clients.aris3_client_sdk.http_client import APIError


class ErrorMapper:
    @staticmethod
    def to_display_message(error: Exception) -> str:
        if isinstance(error, APIError):
            return f"[{error.code}] {error.message} (trace_id={error.trace_id})"
        return str(error)
