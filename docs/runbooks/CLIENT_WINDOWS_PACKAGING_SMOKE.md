# Client Windows Packaging Smoke Runbook

## Purpose

This runbook defines a non-publishing smoke path for Windows packaging of:

- ARIS CORE 3 app (`aris_core_3_app`)
- ARIS Control Center app (`aris_control_center_app`)

The smoke job validates scaffold integrity, enforces preflight checks, and emits deterministic diagnostics artifacts for release triage.

## Local commands (PowerShell)

From repository root:

```powershell
python scripts/ci/validate_python_client_layout.py
python scripts/ci/validate_packaging_scaffold.py
python -m pip install --upgrade pip
pip install -r .\clients\python\requirements.txt
pip install -e .\clients\python\aris3_client_sdk
pip install -e .\clients\python\aris_core_3_app
pip install -e .\clients\python\aris_control_center_app
pwsh .\clients\python\packaging\build_core.ps1 -DryRun -CiMode
pwsh .\clients\python\packaging\build_control_center.ps1 -DryRun -CiMode
```

## Expected dry-run output

Each script prints a deterministic summary and does not attempt installer publishing in dry-run mode:

```text
[DRY-RUN] core packaging summary
  app_name=aris-core-3-app
  version=<resolved_version>
  git_sha=<short_sha>
  output_dir=<repo>\clients\python\packaging\temp\artifacts\core
  rendered_spec=<...>\core_app.rendered.spec
  metadata=<...>\core_packaging_metadata.json
  build_summary=<...>\build_summary.json
  ci_mode=True
  installer_skipped=true
```

Control Center uses the same shape with `aris-control-center-app` and `control_center_packaging_metadata.json`.

## Common failures and exact recovery steps

- **`python executable not found in PATH`**
  1. Install Python 3.11+.
  2. Confirm `python --version` succeeds in the same shell.
  3. Re-run `validate_packaging_scaffold.py` and dry-run scripts.
- **`version file missing` / `version.json must contain a non-empty 'version' value`**
  1. Restore `clients/python/packaging/version.json`.
  2. Ensure it contains a valid `version` field.
  3. Re-run dry-run scripts.
- **`expected entrypoint missing`**
  1. Restore app entrypoint in `clients/python/aris_core_3_app/src/aris_core_3_app/app.py` or `clients/python/aris_control_center_app/src/aris_control_center_app/app.py`.
  2. Re-run dry-run scripts.
- **`spec template missing`**
  1. Restore corresponding spec template under `clients/python/packaging`.
  2. Re-run scaffold validation + dry-run scripts.
- **`output directory is not writable`**
  1. Use writable output path via `-OutDir`.
  2. Confirm write permissions in workspace/temp path.
  3. Re-run dry-run scripts.
- **`pyinstaller executable not found in PATH` (non-dry-run only)**
  1. Install tooling: `pip install pyinstaller`.
  2. Verify `pyinstaller --version` works.
  3. Re-run non-dry-run packaging command.
- **`dist directory is empty` (non-dry-run only)**
  1. Open build logs from diagnostics artifact.
  2. Inspect rendered spec path from dry-run summary.
  3. Fix upstream dependency/spec issues and re-run packaging.

## CI workflow behavior

Workflow: `.github/workflows/clients-packaging-smoke.yml`

- Triggered on both `push` and `pull_request` for:
  - `clients/python/**`
  - `scripts/ci/**`
  - `docs/runbooks/CLIENT_WINDOWS_PACKAGING_SMOKE.md`
  - `.github/workflows/clients-packaging-smoke.yml`
- Also supports manual `workflow_dispatch`.
- Runs on `windows-2025` with Python `3.11`.
- Executes scaffold and client layout validators before dry-run packaging.
- Does **not** publish installers.

### Diagnostics upload guardrail

- The workflow pre-creates workspace diagnostics path:
  - `<GITHUB_WORKSPACE>/clients/python/packaging/temp/artifacts`
- The workflow also mirrors diagnostics to an absolute runner temp path:
  - `<RUNNER_TEMP>/clients-packaging-smoke/<GITHUB_RUN_ID>`
- A placeholder log is always written before dry-runs.
- Post-run diagnostics always write:
  - `_tree.txt` (packaging tree snapshot)
  - `step_outcomes.txt` (core/control-center step outcomes)
- Artifact upload uses `if: always()` and `if-no-files-found: error`.

## Artifact locations

Uploaded artifact bundle: `windows-packaging-smoke-diagnostics`

Included source paths:

- `<GITHUB_WORKSPACE>/clients/python/packaging/temp/artifacts/**`
- `<RUNNER_TEMP>/clients-packaging-smoke/<GITHUB_RUN_ID>/**`

Generated metadata JSON per app (even in dry-run):

- `clients/python/packaging/temp/artifacts/core/core_packaging_metadata.json`
- `clients/python/packaging/temp/artifacts/control_center/control_center_packaging_metadata.json`

## CI triage checklist (5-minute path)

1. Download `windows-packaging-smoke-diagnostics`.
2. Open `step_outcomes.txt` to identify failing dry-run step quickly.
3. Inspect corresponding log:
   - `core/build_core_dryrun.log`
   - `control_center/build_control_center_dryrun.log`
4. Check `_tree.txt` to confirm expected scaffold/files exist.
5. Apply the matching fix in **Common failures and exact recovery steps**.
