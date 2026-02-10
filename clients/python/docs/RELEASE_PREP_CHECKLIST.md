# Desktop Client Release Prep Checklist

## Pre-release checks
- [ ] Install dependencies and run full test suite.
- [ ] Run QA matrix in `--quick` mode.
- [ ] Run QA matrix with full checks against seeded UAT tenant.
- [ ] Run packaging verification and review manifest hashes.
- [ ] Build Core and Control Center Windows artifacts.
- [ ] Perform packaged launch smoke on Windows.
- [ ] Generate support bundle from latest run and verify redaction report.

## Go/No-Go criteria (Day 5)
- [ ] No critical FAIL results in QA matrix.
- [ ] Packaging verification has no unresolved blockers.
- [ ] Runtime launch smoke passes for both executables.
- [ ] Permission-denied states are explicit and stable on key screens.
- [ ] Error dialogs/CLI output include `trace_id` for backend correlation.
