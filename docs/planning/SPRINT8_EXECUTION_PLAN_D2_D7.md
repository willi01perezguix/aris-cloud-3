# Sprint 8 Execution Plan (Day 2–Day 7)

## Day 2 — Core App UX hardening + error-state polish
- **Objective:** stabilize first-mile operator interactions and wire shared telemetry/flags baseline.
- **Deliverables:**
  - Auth/session error-state consistency patch.
  - Loading/error transition polish for core screens.
  - Telemetry + feature flag shared scaffolds integrated in baseline form.
  - Beta readiness gate operational in local and CI paths.
- **Required tests/gates:** core app targeted tests, shared scaffold tests, beta readiness gate run.
- **Done criteria:** zero blocker regressions; gate summary all PASS/WARN only.
- **Rollback/containment if blocked:** disable risky UI path behind default-off flag and retain existing stable flow.

## Day 3 — Control Center RBAC UX hardening + admin safety rails
- **Objective:** reduce admin misconfiguration risk while preserving DENY-first semantics.
- **Deliverables:** deny-state messaging improvements, clearer permissioned action affordances, RBAC safety tests.
- **Required tests/gates:** control center RBAC test pack + contract safety check strict mode.
- **Done criteria:** delegated admin scenarios validated; no tenant-ceiling violations.
- **Rollback/containment if blocked:** revert to prior copy-only behavior while keeping permission checks unchanged.

## Day 4 — Performance pass (startup + key screens) + caching/read optimizations
- **Objective:** establish measurable responsiveness gains without changing API contracts.
- **Deliverables:** startup/key-screen measurements, safe read-path optimizations, telemetry timing captures.
- **Required tests/gates:** deterministic smoke + perf sanity command + no regression in stock/POS flows.
- **Done criteria:** agreed performance budget met or mitigations logged with owner/date.
- **Rollback/containment if blocked:** disable optimization switch via default-off feature flag.

## Day 5 — Packaging/install hardening (Windows) + update channel strategy
- **Objective:** reduce beta onboarding friction and prepare update discipline.
- **Deliverables:** packaging doc fixes, installer sanity updates, update-channel draft policy.
- **Required tests/gates:** packaging scaffold tests + dry-run build verification.
- **Done criteria:** packaging sanity checks pass and install troubleshooting documented.
- **Rollback/containment if blocked:** hold beta package publication and ship known-good build instructions.

## Day 6 — Security/permission abuse tests + resilience drills
- **Objective:** stress critical permission and abuse boundaries before beta candidate gate.
- **Deliverables:** abuse test expansions, resilience drill evidence, triage updates.
- **Required tests/gates:** security gate + targeted RBAC/POS precondition checks + contract strict check.
- **Done criteria:** no uncontained P0/P1 abuse path; mitigations documented for residual risk.
- **Rollback/containment if blocked:** isolate vulnerable path via permission gates and defer enablement.

## Day 7 — Beta candidate gate + release notes + sprint closure
- **Objective:** decide beta candidate readiness with objective evidence.
- **Deliverables:** gate summary, release notes draft, closure artifact package.
- **Required tests/gates:** full beta readiness gate + selected E2E/UAT matrix + CI artifacts archived.
- **Done criteria:** green required checks, approved risk log, and explicit no-contract-break confirmation.
- **Rollback/containment if blocked:** no merge/release; open stabilization loop with owner/date and blocker plan.
