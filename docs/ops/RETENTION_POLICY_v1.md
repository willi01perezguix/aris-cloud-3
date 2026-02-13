# Retention Policy v1 (Operational Artifacts)

## Safety defaults
- Retention audit defaults to **dry-run**.
- Cleanup deletion is only performed with explicit `--apply`.
- Tracked source files are never deleted.

## In-scope paths
- `artifacts/post-ga/**`
- `artifacts/diagnostics/**`
- `tmp/diagnostics/**`
- `clients/python/packaging/temp/**`

## Out-of-scope paths
- Any tracked repository source path.
- Application data paths tied to runtime business state.

## Required outputs
Generated in `artifacts/post-ga/day4/`:
- `retention_audit_summary.json`
- `retention_candidates.csv`
- `retention_actions.log`
- `env_snapshot.json`
- `gate_result.txt`

## Exit behavior
- Non-zero exit only for hard policy violations.
- Informational warnings (e.g., missing optional input directories) do not fail execution.
