class ErrorBanner:
    @staticmethod
    def show(error_payload: dict | str) -> None:
        if isinstance(error_payload, str):
            print(f"[ERROR] code=UI_VALIDATION message={error_payload} trace_id=n/a")
            return
        trace_id = error_payload.get("trace_id") or "n/a"
        print(
            "[ERROR] "
            f"code={error_payload.get('code')} "
            f"message={error_payload.get('message')} "
            f"trace_id={trace_id} "
            f"suggestion={error_payload.get('suggestion')}"
        )
