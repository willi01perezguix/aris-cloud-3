# ARIS Control Center (Sprint 7 Day 6)

## Purpose and scope
Control Center integrates Day 6 operational admin workflows in the Python client app:
- Users management (list/search/create/edit and actions)
- Access-control governance (tenant/store/user policy layers)
- Effective permissions preview + RBAC UI gating (default deny)
- Settings integration (variant labels + return policy)
- Session-level recent operations trace for operator confidence

This implementation keeps backend contracts intact and uses existing `/aris3/admin/*` and `/aris3/access-control/*` routes.

## Run instructions
From `clients/python`:

```bash
python -m apps.control_center.main
```

Required environment variables:
- `ARIS3_API_BASE_URL`
- `ARIS3_ENV_NAME` (optional label)
- `ARIS3_ACCESS_TOKEN` (for pre-auth usage) or login credentials via UI flow

## Users and actions flow
- Load/list users from `GET /aris3/admin/users`
- Create user via `POST /aris3/admin/users` with `Idempotency-Key`
- Edit profile fields via `PATCH /aris3/admin/users/{user_id}`
- High-impact actions via `POST /aris3/admin/users/{user_id}/actions`:
  - `set_status`
  - `set_role`
  - `reset_password`
- All action posts include confirmation + de-duplication key in the UI layer.

## RBAC governance and effective permissions preview
- Clear layer visibility:
  1. Global role template
  2. Tenant policy
  3. Store policy
  4. User override
- DENY precedence is rendered explicitly over ALLOW.
- ADMIN ceiling protection blocks grants not in actor-effective permissions.
- Effective permissions preview supports targeted user + store context.

## Settings pages behavior
### Variant fields
- `var1_label`
- `var2_label`

### Return policy
- `return_window_days`
- `require_receipt`
- `allow_refund_cash/card/transfer`
- `allow_exchange`
- `require_manager_for_exceptions`
- `accepted_conditions`
- `non_reusable_label_strategy`
- `restocking_fee_pct`

Both settings screens:
- Load current values on open
- Validate inputs before save
- Save through PATCH endpoints with idempotency metadata
- Refresh and expose trace/audit references in operation history

## Permission requirements and known limitations
- UI uses effective-permission keys and defaults to deny if key is absent.
- Unauthorized responses are expected and surfaced as actionable errors.
- This scope focuses on integration/service/view-model logic; desktop shell rendering stays lightweight.
