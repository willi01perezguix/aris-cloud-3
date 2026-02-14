from aris_control_2.clients.aris3_client_sdk.http_client import APIError


def print_mutation_success(operation: str, result: dict, highlighted_id: str | None = None) -> None:
    trace_id = result.get("trace_id") or result.get("transaction_id")
    summary = result.get("status") or "ok"
    print(f"[success] operation={operation} summary={summary} trace_id={trace_id}")
    if highlighted_id:
        print(f"[highlight] registro actualizado: {highlighted_id}")


def print_mutation_error(operation: str, error: APIError) -> None:
    print(
        "[mutation-error] "
        f"operation={operation} "
        f"code={error.code} "
        f"message={error.message} "
        f"trace_id={error.trace_id}"
    )
