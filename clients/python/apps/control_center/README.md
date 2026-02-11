# ARIS Control Center (Sprint 8 Day 3)

## Purpose and scope
Control Center Sprint 8 Day 3 hardens admin-critical UX for beta readiness while preserving existing API contracts and RBAC semantics.

## UX state model
Control Center now uses a standardized admin state model:
- loading
- empty
- success
- no-permission
- fatal

Errors are normalized into validation/permission/conflict/network/server/fatal categories with safe-retry gating and expandable technical details (`trace_id`, `code`, `action`, `timestamp`).

## RBAC editor safety model
- Precedence is explicitly shown as:
  1. global template
  2. tenant policy
  3. store policy
  4. user override
- Explicit DENY-overrides-ALLOW warning is displayed whenever deny rules exist.
- Policy change preview exposes allow/deny adds/removes before submit.
- ADMIN ceiling enforcement blocks grants beyond actor-effective permissions with clear reasons.
- High-impact policy changes require confirmation.

## Effective-permissions explainer usage
- Supports selected user and optional store context.
- Displays final decision (`ALLOW`/`DENY`) plus contributing policy layers.
- Highlights explicit deny sources causing blocked access.

## High-impact user action safeguards
Actions covered: `set_status`, `set_role`, `reset_password`.
- Confirmation with target summary
- Optional reason/note context
- In-flight disable and duplicate-submit protection
- Success/failure toasts with trace detail payloads
- Mandatory refresh signal after mutation

## Settings validation and unsaved-change behavior
Variant fields and return policy forms provide:
- field-level validation + summary banner model
- unsaved-change detection
- restore-last-saved action
- save status timestamps
- PATCH saves with idempotency metadata where required by contract

## Telemetry and feature flags
Default-safe (off) feature flags:
- `cc_rbac_editor_v2`
- `cc_permission_explainer_v1`
- `cc_safe_actions_v1`

Telemetry events (non-PII payloads):
- `cc_screen_view`
- `cc_policy_edit_attempt` / `cc_policy_edit_result`
- `cc_user_action_attempt` / `cc_user_action_result`
- `cc_permission_denied`
- `cc_validation_failed`

Flags never bypass permission checks; default deny remains authoritative.

## Contract safety note
No backend contracts were changed. Existing routes are reused under `/aris3/admin/*` and `/aris3/access-control/*`.
