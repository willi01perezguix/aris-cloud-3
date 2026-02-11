# CORE APP UX Audit — Sprint 8 Day 2

## Scope
Client-side UX hardening for ARIS-CORE-3 screens, with backend contracts unchanged.

## Alpha Pain Points and Decisions

| Screen | Pain Point | Severity | User Impact | Decision |
|---|---|---:|---|---|
| Login / session restore | Inconsistent auth errors, weak session context | High | Users retry blindly and raise support tickets | **Fix in Day 2** |
| Stock list / filters | Read failures clear the table entirely; filter state lost | High | Operator loses context and repeats work | **Fix in Day 2** |
| Stock imports / migrate | Validation inconsistent and unclear; payload lost on error | High | Invalid submissions and slow correction loops | **Fix in Day 2** |
| POS checkout dialog | Payment rule failures buried; missing actionable feedback | High | Failed checkout attempts and confusion | **Fix in Day 2** |
| POS cash session & movements | State/permission feedback inconsistent | Medium | Unsafe actions attempted repeatedly | **Fix in Day 2** |
| Global notifications/errors | No single taxonomy of validation/permission/network/server failures | High | Uneven UX and difficult support/debug | **Fix in Day 2** |
| Keyboard workflow optimization | Limited shortcut discoverability beyond core paths | Low | Slower expert operation | **Defer** |
| Rich recovery wizard for uncertain mutations | Needs product/ops policy review | Medium | Better ambiguity resolution but larger scope | **Defer** |

## Before / After Behavior Notes

### Login / Session Restore
- **Before:** generic failure text only.
- **After:** login telemetry hooks (`auth_login_result`), route-level status, and shell context visibility maintained.

### Stock List + Filters + Imports + Migrate
- **Before:** read errors removed all data; no standard view-state contract; weak inline validation.
- **After:** standardized state payloads (`loading/empty/success/partial_error/fatal_error/no_permission`), optional optimistic snapshot retention via flag, filter persistence on refresh, and shared validators (EPC 24-HEX, EPC qty=1, SKU qty positive).

### POS Sales Checkout / Payment Dialog
- **Before:** mixed validation paths and less explicit payload preservation.
- **After:** validation summary + field-level errors, preserved entered payment values, mutation failure marked `not_applied`, and checkout rule enforcement surfaced clearly.

### POS Cash Session and Movements
- **Before:** limited state model, no standardized view-state output.
- **After:** unified state rendering + guardrails for action availability and confirmation requirements.

### Global Notifications / Errors
- **Before:** ad-hoc error strings.
- **After:** shared error presenter categories, technical detail envelope (code/trace_id/action/timestamp), and retry panel safety model.

## Deferred Items
1. Full keyboard command palette and configurable shortcuts.
2. Guided recovery flow for mutation uncertainty with operator acknowledgment workflow.
3. Cross-screen breadcrumb replay for deep-linked recovery.
