from __future__ import annotations

from ui.shared.error_presenter import ErrorPresenter
from ui.shared.retry_panel import RetryPanel


def test_error_presenter_maps_categories() -> None:
    presenter = ErrorPresenter()

    denied = presenter.present(message="Permission denied", details={"code": "PERMISSION_DENIED"}, trace_id="t1", action="x")
    timeout = presenter.present(message="network timeout", details={"code": "TIMEOUT"}, trace_id="t2", action="x", allow_retry=True)
    validation = presenter.present(message="invalid qty", details={"code": "VALIDATION"}, trace_id="t3", action="x")

    assert denied.category == "permission_denied"
    assert timeout.category == "transport"
    assert timeout.safe_to_retry is True
    assert validation.category == "validation"
    assert denied.details["trace_id"] == "t1"


def test_retry_panel_enabled_only_for_safe_scenarios() -> None:
    read_retry = RetryPanel(operation="stock.load", is_mutation=False, idempotent=True, has_transient_error=True)
    unsafe_mutation = RetryPanel(operation="sale.checkout", is_mutation=True, idempotent=False, has_transient_error=True)

    assert read_retry.render()["enabled"] is True
    assert unsafe_mutation.render()["enabled"] is False
