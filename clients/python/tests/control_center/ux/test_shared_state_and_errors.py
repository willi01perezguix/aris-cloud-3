from __future__ import annotations

from apps.control_center.ui.shared.error_presenter import AdminErrorPresenter
from apps.control_center.ui.shared.retry_panel import SafeRetryPanel
from apps.control_center.ui.shared.view_state import AdminViewStatus, resolve_admin_view_state


def test_standardized_error_state_rendering() -> None:
    presenter = AdminErrorPresenter()
    err = presenter.present(message="validation failed", action="settings.save", code="invalid", allow_retry=True)
    assert err.category == "validation"
    assert err.safe_to_retry is False
    expanded = err.render(expanded=True)
    assert expanded["technical_details"]["action"] == "settings.save"


def test_loading_empty_no_permission_fatal_states() -> None:
    assert resolve_admin_view_state(can_view=False, loading=False, has_data=False, error=None).status == AdminViewStatus.NO_PERMISSION
    assert resolve_admin_view_state(can_view=True, loading=True, has_data=False, error=None).status == AdminViewStatus.LOADING
    assert resolve_admin_view_state(can_view=True, loading=False, has_data=False, error=None).status == AdminViewStatus.EMPTY
    assert resolve_admin_view_state(can_view=True, loading=False, has_data=False, error="boom").status == AdminViewStatus.FATAL


def test_retry_enabled_only_when_safe() -> None:
    assert SafeRetryPanel(action="load", transient_error=True, is_mutation=False, idempotent=True).can_retry() is True
    assert SafeRetryPanel(action="mutate", transient_error=True, is_mutation=True, idempotent=False).can_retry() is False
