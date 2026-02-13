# Incident Reporting Playbook (Post-Hypercare Baseline)

## Purpose
Standardize incident declaration, communication, escalation, and closure now that hypercare has ended.

## Trigger criteria
Declare an incident when any apply:
- Customer-visible API degradation sustained > 5 minutes.
- SLA/SLO burn rate exceeds error budget alert thresholds.
- Cross-tenant risk, RBAC breach risk, or audit integrity concern.

## Reporting workflow
1. Declare incident in bridge channel with unique incident ID.
2. Capture time detected, impacted services, severity, and tenant scope.
3. Assign incident commander and communications lead.
4. Post updates every 15 minutes (P0/P1) or 60 minutes (P2).
5. Publish closure summary and RCA within 24 hours.

## Escalation contacts matrix
| Role | Primary | Secondary | Responsibility |
|---|---|---|---|
| On-call SRE | SRE rotation | Backup SRE | Initial triage + mitigation |
| Service owner | Platform owner | Backend lead | Service-level remediation |
| Incident commander | Duty manager | Engineering manager | Coordination + decision gate |
| Executive notification | VP Engineering delegate | Product director | External stakeholder comms |

## RCA minimum template
- Incident timeline (UTC)
- Detection source
- Root cause
- Contributing factors
- Corrective actions
- Preventive actions and owner + due date

## Handoff requirements to steady-state ops
- Confirm monitoring ownership and paging schedules.
- Confirm runbook coverage for top 10 incident classes.
- Confirm incident metrics dashboard and weekly review owner.
