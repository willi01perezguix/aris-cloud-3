# Client Python CI Guardrails

## Canonical deterministic install commands
Run from repository root:

```bash
python scripts/ci/validate_python_client_layout.py
python -m pip install --upgrade pip
pip install -r ./clients/python/requirements.txt
pip install -e ./clients/python/aris3_client_sdk
pip install -e ./clients/python/aris_core_3_app
pip install -e ./clients/python/aris_control_center_app
```

## Common failures and fixes

- **Missing client subproject directory or `pyproject.toml`**
  - Error points to exact missing path.
  - Restore the missing folder/file or update the planned client install matrix.

- **Blocked workflow pattern (`clients/python[dev]` or `aris3_client_sdk[dev]`)**
  - Replace with canonical editable installs using explicit subproject paths from repo root.

- **Invalid editable entry in `clients/python/requirements.txt`**
  - Keep this file dependency-only.
  - Put editable installs in workflow/local helper commands only.

## Local reproducible check script

Use PowerShell from any directory:

```powershell
pwsh ./scripts/dev/check_clients_ci.ps1
```

The script runs layout guardrails, deterministic installs, and targeted `clients/python/tests` checks with a concise pass/fail summary.
