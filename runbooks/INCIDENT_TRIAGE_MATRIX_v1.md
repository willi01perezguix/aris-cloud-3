# Incident Triage Matrix v1

## Severity Matrix
| Severity | Trigger Examples | Customer Impact | Initial Owner | Update Cadence |
|---|---|---|---|---|
| SEV0 | Platform unavailable, data integrity/compliance threat | Critical / global | Incident Commander + Ops | Every 15 min |
| SEV1 | Core flows degraded (POS checkout/report exports) | High / multi-tenant | Dev On-call | Every 30 min |
| SEV2 | Non-critical module degraded with workaround | Medium / scoped | Feature owner | Hourly |
| SEV3 | Cosmetic/minor bug | Low | Backlog owner | Daily |

## Triage Steps
1. Capture UTC timestamp, SHA, impacted tenants/users.
2. Assign severity using matrix.
3. Determine path:
   - rollback-first when safe and faster to recover.
   - forward-fix only when no contract/business drift.
4. Validate via smoke gate scripts and targeted tests.
5. Communicate status using incident templates.

## SLA Targets
| Severity | Ack | Mitigation Start | Recovery Target |
|---|---:|---:|---:|
| SEV0 | 5 min | 10 min | 30 min |
| SEV1 | 10 min | 20 min | 60 min |
| SEV2 | 30 min | 60 min | 4 hours |
| SEV3 | 1 business day | Planned | Sprint window |

## Communication Checklist
- [ ] Incident start posted.
- [ ] Regular updates posted per cadence.
- [ ] Resolution post includes validation evidence and next actions.
