# Sprint 7 Board Template

## Kanban Columns
1. **Backlog** — triaged but not ready to pull.
2. **Ready** — meets Definition of Ready and can be started.
3. **In Progress** — actively being implemented by an assigned owner.
4. **Review** — implementation complete, pending code/product review.
5. **Done** — accepted with evidence and merged.
6. **Blocked** — cannot proceed due to dependency/risk requiring escalation.

## Definition of Ready (DoR)
A card may enter **Ready** only when all are true:
- Problem statement and user impact are explicit.
- Scope and non-goals are defined.
- Acceptance criteria are testable.
- Owner is assigned (or explicitly marked temporary owner).
- Dependencies and risks are identified.
- Contract-safety implications are documented (if API/app integration involved).

## Definition of Done (DoD)
A card may enter **Done** only when all are true:
- Acceptance criteria fully met.
- Required tests/gates pass and evidence is attached.
- Documentation/changelog updated where applicable.
- Security/RBAC implications reviewed for affected flows.
- No frozen contract rule violation introduced.
- Reviewer sign-off recorded.

## Blocker escalation policy
- If blocked **> 4 working hours**, move card to **Blocked** with blocker type and dependency owner.
- If blocked **> 1 day**, escalate to sprint lead in daily checkpoint with:
  - blocker summary,
  - impact on P0 delivery,
  - proposed containment/rollback path,
  - requested decision deadline.
- If blocker affects frozen contract or production safety, escalate immediately (same day) and freeze dependent merges until resolved.

## Suggested card metadata
- ID
- Priority (P0/P1/P2/Deferred)
- Module
- Owner
- Risk (Low/Medium/High)
- Effort (S/M/L)
- Dependencies
- Evidence links (tests, logs, screenshots where applicable)
