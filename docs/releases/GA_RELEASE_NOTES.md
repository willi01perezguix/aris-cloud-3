# GA Release Notes

## Release Summary
- Release target: `0.1.0` (GA)
- Type: Release finalization and operational handoff
- Scope: Documentation, release gate workflow, release gate scripts, and release manifest

## Included Scope
- GA readiness report and test evidence bundle.
- GA deployment handoff runbook with prerequisites, rollback triggers, and ownership checklists.
- Manual `workflow_dispatch` GA release-gate GitHub Actions workflow.
- Cross-platform GA gate scripts (`bash` and PowerShell) producing `artifacts/ga/` outputs.

## Explicit Non-Goals
- No endpoint, payload, or schema changes.
- No business-rule changes for stock/transfers/POS/reports.
- No broad refactors.

## Contract Safety Statement
**No API contract drift introduced in this GA package.**

## Tagging Commands (Maintainer-Executed)
> Do not run automatically from this branch; execute after merge and final verification.

```bash
git checkout main
git pull --rebase origin main
git tag -a v0.1.0 -m "ARIS Cloud 3 GA 0.1.0"
git push origin v0.1.0
```

## Draft Release Notes Command (Maintainer)
```bash
gh release create v0.1.0 \
  --draft \
  --title "ARIS Cloud 3 GA 0.1.0" \
  --notes-file docs/releases/GA_RELEASE_NOTES.md
```
