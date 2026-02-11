from __future__ import annotations

from apps.control_center.app.state import OperationRecord


def summarize_operation(record: OperationRecord) -> str:
    refs = [f"action={record.action}", f"target={record.target}"]
    if record.trace_id:
        refs.append(f"trace={record.trace_id}")
    if record.idempotency_key:
        refs.append(f"idempotency={record.idempotency_key}")
    if record.transaction_id:
        refs.append(f"txn={record.transaction_id}")
    return " | ".join(refs)
