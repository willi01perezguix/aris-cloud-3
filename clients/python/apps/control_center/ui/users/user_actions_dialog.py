from __future__ import annotations


HIGH_IMPACT_ACTIONS = {"set_status", "set_role", "reset_password"}


def requires_confirmation(action: str) -> bool:
    return action in HIGH_IMPACT_ACTIONS


def action_dedupe_key(user_id: str, action: str, transaction_id: str | None = None) -> str:
    return f"{user_id}:{action}:{transaction_id or 'no-txn'}"
