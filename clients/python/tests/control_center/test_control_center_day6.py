from __future__ import annotations

from dataclasses import dataclass

from aris3_client_sdk.exceptions import ApiError

from apps.control_center.app.navigation import build_navigation
from apps.control_center.app.state import SessionState
from apps.control_center.services.access_control_service import AccessControlService, blocked_admin_grants, deny_wins
from apps.control_center.services.admin_users_service import AdminUsersService
from apps.control_center.services.settings_service import SettingsService
from apps.control_center.ui.access.effective_permissions_view import format_effective_permissions
from apps.control_center.ui.access.roles_policies_view import block_for_admin_ceiling, resolve_precedence
from apps.control_center.ui.settings.return_policy_view import ReturnPolicyForm
from apps.control_center.ui.settings.variant_fields_view import VariantFieldsForm
from apps.control_center.ui.users.user_actions_dialog import action_dedupe_key, requires_confirmation
from apps.control_center.ui.users.user_editor_view import validate_create_user, validate_edit_user
from apps.control_center.ui.users.users_list_view import UsersListViewModel
from apps.control_center.ui.widgets.audit_trace_panel import summarize_operation


@dataclass
class FakeAdminClient:
    users: list[dict]

    def __post_init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    def _request(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        if method == "GET" and path == "/aris3/admin/users":
            return {"users": self.users, "trace_id": "trace-users"}
        if method == "POST" and path == "/aris3/admin/users":
            payload = kwargs["json"]
            return {"user": {"id": "new-user", **payload}, "trace_id": "trace-create"}
        if method == "PATCH" and path.startswith("/aris3/admin/users/") and not path.endswith("/actions"):
            return {"user": {"id": path.split("/")[-1], **kwargs["json"]}, "trace_id": "trace-edit"}
        if method == "POST" and path.endswith("/actions"):
            return {
                "user": {"id": path.split("/")[-2], "status": "SUSPENDED", "role": "MANAGER"},
                "trace_id": "trace-action",
                "action": kwargs["json"]["action"],
            }
        if path.endswith("/variant-fields") and method == "GET":
            return {"var1_label": "Color", "var2_label": "Size", "trace_id": "trace-variant"}
        if path.endswith("/variant-fields") and method == "PATCH":
            return {**kwargs["json"], "trace_id": "trace-variant-save"}
        if path.endswith("/return-policy") and method == "GET":
            return {
                "return_window_days": 30,
                "require_receipt": True,
                "allow_refund_cash": True,
                "allow_refund_card": True,
                "allow_refund_transfer": False,
                "allow_exchange": True,
                "require_manager_for_exceptions": False,
                "accepted_conditions": ["NEW"],
                "non_reusable_label_strategy": "ASSIGN_NEW_EPC",
                "restocking_fee_pct": 0,
                "trace_id": "trace-rp",
            }
        if path.endswith("/return-policy") and method == "PATCH":
            return {**kwargs["json"], "trace_id": "trace-rp-save"}
        if path == "/aris3/admin/access-control/effective-permissions":
            return {
                "permissions": [
                    {"key": "USER_MANAGE", "allowed": False, "source": "tenant_policy_deny"},
                    {"key": "AUDIT_VIEW", "allowed": True, "source": "user_override_allow"},
                ],
                "sources_trace": {
                    "template": {"allow": ["USER_MANAGE"], "deny": []},
                    "tenant": {"allow": [], "deny": ["USER_MANAGE"]},
                    "store": {"allow": [], "deny": []},
                    "user": {"allow": ["AUDIT_VIEW"], "deny": []},
                },
            }
        if "conflict" in kwargs.get("json", {}):
            raise ApiError(status_code=409, message="conflict", code="CONFLICT")
        return {"trace_id": "trace-generic"}


@dataclass
class FakeAccessClient:
    def effective_permissions_for_user(self, user_id: str):
        class Response:
            def model_dump(self, mode: str = "json"):
                return {
                    "permissions": [{"key": "USER_MANAGE", "allowed": True, "source": "role_template"}],
                    "sources_trace": {
                        "template": {"allow": ["USER_MANAGE"], "deny": []},
                        "tenant": {"allow": [], "deny": []},
                        "store": {"allow": [], "deny": []},
                        "user": {"allow": [], "deny": []},
                    },
                }

        return Response()


def test_users_list_load_search_render() -> None:
    vm = UsersListViewModel(users=[{"username": "alice", "email": "a@x"}, {"username": "bob", "email": "b@x"}], query="ali")
    assert [row["username"] for row in vm.filtered] == ["alice"]


def test_user_create_edit_flow_validation() -> None:
    assert "password" in validate_create_user({"username": "u", "email": "u@example.com", "password": "123"})
    assert "email" in validate_edit_user({"email": ""})


def test_user_actions_wiring_set_status_set_role_reset_password() -> None:
    state = SessionState(actor="admin")
    admin = FakeAdminClient(users=[])
    service = AdminUsersService(admin, state)  # type: ignore[arg-type]

    for action in ("set_status", "set_role", "reset_password"):
        result = service.user_action("u1", {"action": action, "transaction_id": "txn-1"}, idempotency_key=f"idem-{action}")
        assert result.operation.action.endswith(action)
        assert requires_confirmation(action) is True


def test_rbac_precedence_rendering_deny_over_allow() -> None:
    resolved = resolve_precedence({"USER_MANAGE", "AUDIT_VIEW"}, {"USER_MANAGE"})
    assert resolved["USER_MANAGE"] is False
    assert deny_wins([
        {"key": "USER_MANAGE", "allowed": True, "source": "role_template"},
        {"key": "USER_MANAGE", "allowed": False, "source": "tenant_policy_deny"},
    ])["USER_MANAGE"] is False


def test_admin_ceiling_behavior_blocked_grants() -> None:
    blocked = blocked_admin_grants({"AUDIT_VIEW"}, {"AUDIT_VIEW", "USER_MANAGE"})
    assert blocked == {"USER_MANAGE"}
    assert "USER_MANAGE" in block_for_admin_ceiling({"AUDIT_VIEW"}, {"USER_MANAGE"})


def test_effective_permissions_preview_flow() -> None:
    state = SessionState(actor="admin")
    service = AccessControlService(FakeAccessClient(), FakeAdminClient(users=[]), state)  # type: ignore[arg-type]
    payload = service.effective_permissions_for_user("u-1", store_id="store-1")
    rows = format_effective_permissions(payload)
    assert any("DENY" in row for row in rows)
    layered = service.build_layered_view(payload)
    assert "USER_MANAGE" in layered.tenant_deny


def test_settings_load_save_variant_fields() -> None:
    state = SessionState(actor="admin")
    service = SettingsService(FakeAdminClient(users=[]), state)  # type: ignore[arg-type]
    current = service.load_variant_fields()
    form = VariantFieldsForm(current["var1_label"], current["var2_label"])
    assert form.validate() == {}
    saved = service.save_variant_fields({"var1_label": "Color"}, idempotency_key="idem-1")
    assert saved.operation.idempotency_key == "idem-1"


def test_settings_load_save_return_policy_with_validation() -> None:
    state = SessionState(actor="admin")
    service = SettingsService(FakeAdminClient(users=[]), state)  # type: ignore[arg-type]
    current = service.load_return_policy()
    form = ReturnPolicyForm({**current, "restocking_fee_pct": -1})
    assert "restocking_fee_pct" in form.validate()
    saved = service.save_return_policy({"return_window_days": 14}, idempotency_key="idem-rp")
    assert saved.payload["return_window_days"] == 14


def test_permission_gated_ui_hides_unauthorized_controls_default_deny() -> None:
    nav = build_navigation({"USER_MANAGE"})
    nav_map = {item.label: allowed for item, allowed, _ in nav}
    assert nav_map["Users"] is True
    assert nav_map["Access Control"] is False


def test_mapped_api_errors_show_actionable_feedback() -> None:
    state = SessionState(actor="admin")
    service = AdminUsersService(FakeAdminClient(users=[]), state)  # type: ignore[arg-type]
    try:
        service.update_user("u-1", {"conflict": True})
    except ApiError as exc:
        assert exc.status_code == 409

    service.create_user(
        {"username": "alice", "email": "a@example.com", "password": "Pass1234!", "role": "USER"},
        idempotency_key="idem-create",
    )
    summary = summarize_operation(state.operations[0])
    assert "idempotency=idem-create" in summary
    assert action_dedupe_key("u-1", "set_status", "txn-1") == "u-1:set_status:txn-1"
