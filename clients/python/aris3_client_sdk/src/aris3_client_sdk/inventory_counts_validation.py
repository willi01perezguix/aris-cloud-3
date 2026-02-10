from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .models_inventory_counts import CountActionRequest, CountCreateRequest, CountState, ReconcileRequest, ScanBatchRequest
from .stock_validation import normalize_epc


@dataclass(frozen=True)
class ValidationIssue:
    row_index: int | None
    field: str
    reason: str


class ClientValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        super().__init__("inventory counts validation failed")
        self.issues = issues


def validate_start_payload(payload: CountCreateRequest | Mapping[str, Any]) -> CountCreateRequest:
    candidate = payload if isinstance(payload, CountCreateRequest) else CountCreateRequest.model_validate(payload)
    issues: list[ValidationIssue] = []
    if not candidate.store_id or not candidate.store_id.strip():
        issues.append(ValidationIssue(row_index=None, field="store_id", reason="store_id is required"))
    if issues:
        raise ClientValidationError(issues)
    return candidate


def validate_scan_batch_payload(payload: ScanBatchRequest | Mapping[str, Any]) -> ScanBatchRequest:
    candidate = payload if isinstance(payload, ScanBatchRequest) else ScanBatchRequest.model_validate(payload)
    issues: list[ValidationIssue] = []
    if not candidate.items:
        issues.append(ValidationIssue(row_index=None, field="items", reason="scan batch cannot be empty"))

    normalized_items = []
    for idx, item in enumerate(candidate.items):
        has_epc = bool(item.epc and item.epc.strip())
        has_sku = bool(item.sku and item.sku.strip())
        if not has_epc and not has_sku:
            issues.append(ValidationIssue(row_index=idx, field="epc/sku", reason="either epc or sku is required"))
        if item.qty <= 0:
            issues.append(ValidationIssue(row_index=idx, field="qty", reason="qty must be > 0"))
        normalized = item.model_copy()
        if has_epc:
            normalized = normalized.model_copy(update={"epc": normalize_epc(item.epc)})
        normalized_items.append(normalized)

    if issues:
        raise ClientValidationError(issues)
    return candidate.model_copy(update={"items": normalized_items})


def validate_reconcile_payload(payload: ReconcileRequest | Mapping[str, Any] | None = None) -> ReconcileRequest:
    source = payload or {}
    candidate = source if isinstance(source, ReconcileRequest) else ReconcileRequest.model_validate(source)
    if candidate.action.upper() != "RECONCILE":
        raise ClientValidationError([ValidationIssue(row_index=None, field="action", reason="action must be RECONCILE")])
    return candidate


def validate_action_state_intent(current_state: str | CountState | None, action: str) -> CountActionRequest:
    desired = action.upper()
    allowed_by_state: dict[str, set[str]] = {
        "DRAFT": {"START", "CANCEL"},
        "ACTIVE": {"PAUSE", "CLOSE", "CANCEL"},
        "PAUSED": {"RESUME", "CLOSE", "CANCEL"},
        "CLOSED": {"RECONCILE"},
        "RECONCILED": set(),
        "CANCELLED": set(),
    }
    state_value = current_state.value if isinstance(current_state, CountState) else (current_state or "").upper()
    allowed = allowed_by_state.get(state_value)
    if allowed is None:
        raise ClientValidationError([ValidationIssue(row_index=None, field="state", reason=f"unknown state '{current_state}'")])
    if desired not in allowed:
        raise ClientValidationError(
            [ValidationIssue(row_index=None, field="action", reason=f"action {desired} is not allowed from {state_value}")]
        )
    return CountActionRequest(action=desired)
