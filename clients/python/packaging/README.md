# Windows Packaging

## Prerequisites
- Python 3.11+
- `pip install pyinstaller`

## Version source
- `version.json` is default source.
- Override with `PACKAGING_APP_VERSION` (or `ARIS_APP_VERSION`).

## Build
```powershell
cd clients/python/packaging
./build_core.ps1
./build_control_center.ps1
# or
./build_all.ps1
```

Dry-run preflight:
```powershell
./build_core.ps1 -DryRun
./build_control_center.ps1 -DryRun
```

## Reliability hardening behaviors
- Scripts use strict mode (`Set-StrictMode -Version Latest`) and fail fast on native command errors.
- Preflight validates required files (`version.json`, app entrypoint, and `*.spec.template`) before build execution.
- Output directory writability is explicitly validated.
- Metadata and build summary JSON outputs are validated after write.
- Non-dry-run mode validates `pyinstaller` availability and ensures `dist/` exists with non-empty file outputs.

## Output conventions
- `dist/core/`
- `dist/control_center/`
- each build writes `build_summary.json`

## Installer scaffold
If installer tooling is unavailable, run:
```powershell
./installer_placeholder.ps1
```

## Sprint 7 Day 7 internal alpha naming
- Core artifact: `aris-core3-alpha-s7d7-<build>`
- Control Center artifact: `control-center-alpha-s7d7-<build>`

Recommended sequence:
```powershell
./build_core.ps1 -DryRun
./build_control_center.ps1 -DryRun
./build_core.ps1
./build_control_center.ps1
```
