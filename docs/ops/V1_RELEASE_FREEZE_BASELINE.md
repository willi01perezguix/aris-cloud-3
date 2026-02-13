# v1 Release Freeze Baseline

## Baseline Intent
This baseline freezes ARIS v1 API and domain behavior so post-GA operations can continue without release drift.

## Locked Contract Baseline
- All `/aris3/*` v1 route paths currently present in GA.
- Existing request/response schemas and status-code semantics.
- Existing pagination/filter/query parameter contracts.
- Existing `GET /aris3/stock` full-table contract output shape and meaning.

## Locked Business Invariants
- Inventory write and stock movement rules remain unchanged.
- Transfer flow state machine remains under `/actions` transition endpoints.
- POS sales/cash/reports calculations, scoping, and audit event expectations remain unchanged.
- Idempotency semantics, tenant isolation, and RBAC boundary enforcement remain unchanged.

## Frozen Runtime Controls
- Protected DB migration policy (expand-safe only unless explicitly approved).
- Audit trails and access checks cannot be bypassed by release shortcuts.
- Operational runbooks, ownership matrix, and SEV escalation targets are baseline obligations.

## Controlled v1.1 Intake
All v1.1 candidates must follow `docs/ops/V1_1_CHANGE_INTAKE_POLICY.md` and include traceable evidence before entering a release train.
