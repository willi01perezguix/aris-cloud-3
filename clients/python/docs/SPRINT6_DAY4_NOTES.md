# Sprint 6 Day 4 Notes

## Hardening changes
- SDK timeout settings split into connect/read values with env overrides.
- Retry policy restricted to idempotent read methods (`GET/HEAD/OPTIONS`).
- API error string output now includes `trace_id` when present.
- Added standardized UI error adapter (`to_user_facing_error`) and wired it into key CORE screens.
- Added QA matrix runner scaffold and support bundle utility.
- Added packaging verification script that writes deterministic manifest/report artifacts.

## QA/packaging result summary
- QA runner now emits JSON + Markdown matrix artifacts under `artifacts/qa/`.
- Packaging verification emits build manifest + verification report under `artifacts/packaging/`.
- Support bundle emits redacted diagnostics ZIP under `artifacts/support/`.

## Known issues / Day 5 plan
- Full authenticated matrix execution needs seeded test credentials + data.
- Windows `.ps1` build runtime smoke must run on Windows host for executable launch validation.
- Expand UI smoke tests for more destructive-action confirmation paths.
