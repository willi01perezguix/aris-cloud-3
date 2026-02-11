# Client Windows Packaging Smoke Runbook

## Purpose

This runbook defines a non-publishing smoke path for Windows packaging of:

- ARIS CORE 3 app (`aris_core_3_app`)
- ARIS Control Center app (`aris_control_center_app`)

The smoke job validates scaffold integrity, enforces preflight checks, and emits metadata artifacts for future release automation.

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
  ci_mode=True
  installer_skipped=true
```

Control Center uses the same shape with `aris-control-center-app` and `control_center_packaging_metadata.json`.

## Common failures and fixes

- **`python executable not found in PATH`**
  - Install Python 3.11+ and ensure `python` resolves in shell.
- **`expected entrypoint missing`**
  - Restore app entrypoint in `clients/python/aris_core_3_app/src/aris_core_3_app/app.py` or `clients/python/aris_control_center_app/src/aris_control_center_app/app.py`.
- **`spec template missing`**
  - Restore corresponding spec template under `clients/python/packaging`.
- **`output directory is not writable`**
  - Use a writable output path (`-OutDir`) or fix workspace permissions.
- **scaffold validator missing files**
  - Recreate removed packaging files and required client `pyproject.toml` files.

## CI workflow behavior

Workflow: `.github/workflows/clients-packaging-smoke.yml`

- Triggered by pull requests touching:
  - `clients/python/**`
  - `scripts/ci/**`
  - `.github/workflows/**`
- Also supports manual `workflow_dispatch`.
- Runs on `windows-latest` with Python `3.11`.
- Executes scaffold and client layout validators before dry-run packaging.
- Does **not** publish installers.

## Artifact locations

Uploaded artifact bundle: `windows-packaging-smoke-diagnostics`

Included path:

- `clients/python/packaging/temp/artifacts/**`

Generated metadata JSON per app (even in dry-run):

- `clients/python/packaging/temp/artifacts/core/core_packaging_metadata.json`
- `clients/python/packaging/temp/artifacts/control_center/control_center_packaging_metadata.json`
