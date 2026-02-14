class ErrorBanner:
    @staticmethod
    def show(error_payload: dict | str) -> None:
        if isinstance(error_payload, str):
            print(f"[ERROR] {error_payload}")
            return
        print(
            "[ERROR] "
            f"code={error_payload.get('code')} "
            f"message={error_payload.get('message')} "
            f"details={error_payload.get('details')} "
            f"trace_id={error_payload.get('trace_id')}"
        )
