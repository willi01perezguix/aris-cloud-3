# On-Call Ownership Matrix (v1)

## Ownership Matrix
| Domain | Accountable Role | Primary | Backup | Escalation |
|---|---|---|---|---|
| API Platform | `<platform-accountable>` | `<platform-primary>` | `<platform-backup>` | `<eng-director>` |
| Data/DB | `<data-accountable>` | `<dba-primary>` | `<dba-backup>` | `<cto>` |
| Security/RBAC | `<security-accountable>` | `<security-primary>` | `<security-backup>` | `<ciso>` |
| Reports/Exports | `<reports-accountable>` | `<reports-primary>` | `<reports-backup>` | `<product-lead>` |
| POS/Store Ops | `<pos-accountable>` | `<pos-primary>` | `<pos-backup>` | `<ops-lead>` |

## SEV Response Expectations
- SEV-1: acknowledge ≤ 5 minutes, mitigation owner assigned ≤ 10 minutes, escalation started ≤ 15 minutes.
- SEV-2: acknowledge ≤ 15 minutes, mitigation owner assigned ≤ 30 minutes.
- SEV-3: acknowledge ≤ 60 minutes, mitigation owner assigned same business day.

## Escalation SLA Targets
- SEV-1 stakeholder update every 30 minutes.
- SEV-2 stakeholder update every 60 minutes.
- Incident commander required for all SEV-1 and optional for SEV-2.

## Handoff Requirements
- Every shift has named primary + backup.
- Active incidents include status, owner, next action, and ETA in handoff note.
- Post-incident action items assigned within 24 hours.
