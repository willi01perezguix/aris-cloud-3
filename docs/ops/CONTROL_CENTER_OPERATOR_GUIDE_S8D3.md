# Control Center Operator Guide — Sprint 8 Day 3

## 1) Safe RBAC policy editing
1. Open Access Control and verify selected tenant/store context.
2. Review precedence banner: `global template -> tenant policy -> store policy -> user override`.
3. Inspect change preview (allow/deny added/removed) before submit.
4. If warning says a grant exceeds ADMIN tenant ceiling, remove blocked permission and retry.
5. Confirm high-impact changes only after validating deny-over-allow consequences.

## 2) Effective permission investigation (why allowed/denied)
1. Select user and optional store context.
2. Open effective-permissions explainer rows.
3. Confirm final decision and contributing source layers.
4. If denied, inspect explicit deny layer markers and trace id details.

## 3) High-impact user actions
Actions covered: `set_status`, `set_role`, `reset_password`.
1. Verify target summary in confirmation dialog.
2. Add optional reason/note to improve audit context.
3. Submit once; buttons are disabled while request is in-flight.
4. Review success/failure toast and technical trace details.
5. Refresh users list after completion (mandatory).

## 4) Settings safe operation
### Variant fields and return policy
1. Edit fields and monitor inline validation + summary banner.
2. If navigation is attempted with unsaved edits, stop and save or restore last saved values.
3. Use restore action to recover previous persisted values.
4. Confirm save status and timestamp after successful PATCH response.

## 5) Error and retry playbook
- Retry only when state indicates transient network/server category and safe operation metadata permits retry.
- For conflict/validation/permission errors, do not blind-retry; resolve input or authorization first.
- Capture trace_id/code/action/timestamp from technical details for incident escalation.
