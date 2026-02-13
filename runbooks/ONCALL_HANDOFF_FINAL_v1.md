# On-Call Handoff Final v1

## Ownership / Rotation Metadata
- Primary owner: `<team-or-user>`
- Secondary owner: `<team-or-user>`
- Rotation timezone: `<timezone>`
- Escalation manager: `<name>`
- Effective date: `<YYYY-MM-DD>`

## First 15 minutes triage checklist
1. Acknowledge incident and declare severity (SEV1/SEV2/SEV3).
2. Confirm scope (tenant, endpoint, region, data-path).
3. Validate health checks and latest deploy/hotfix history.
4. Check Day-4 governance artifacts for budget and retention anomalies.
5. Decide: stabilize, rollback-first, or continue diagnosis.

## Rollback decision tree
- User-impacting outage or data-risk present?
  - Yes -> rollback-first to last known good release.
  - No -> continue mitigations with bounded timebox.
- Contract drift suspected?
  - Yes -> immediate rollback and contract safety verification.
  - No -> proceed with runbook triage.

## Internal incident update template
- `Status`: Investigating / Mitigating / Monitoring / Resolved
- `Severity`: SEVx
- `Impact`: who/what is affected
- `Timeline`: UTC checkpoints
- `Actions`: rollback/hotfix/guardrails applied
- `Next update`: UTC timestamp

## Handoff completion checklist
- [ ] Ownership placeholders replaced with real values.
- [ ] Rotation coverage validated for all time windows.
- [ ] Escalation contacts tested.
- [ ] SEV matrix acknowledged by on-call team.
- [ ] Rollback procedure dry-run complete.
- [ ] Day-4 governance workflow access confirmed.
