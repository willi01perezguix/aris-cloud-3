# SEV Triage Matrix v1

## Severity definitions
- **SEV1**: Broad outage, critical business path unavailable, or high confidence data integrity risk.
- **SEV2**: Major degradation with workaround, limited but meaningful business impact.
- **SEV3**: Minor degradation, low-risk issue, no immediate critical business interruption.

## Response expectations
- SEV1: immediate incident bridge + rollback decision in first 15 minutes.
- SEV2: triage owner assigned within 15 minutes; mitigation plan within 60 minutes.
- SEV3: queued remediation with monitoring and communication in normal ops cadence.

## Escalation guidance
- Escalate to SEV1 if customer-impact expands or data integrity uncertainty appears.
- De-escalate only after stable metrics and explicit owner confirmation.
