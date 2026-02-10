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

## Output conventions
- `dist/core/`
- `dist/control_center/`
- each build writes `build_summary.json`

## Installer scaffold
If installer tooling is unavailable, run:
```powershell
./installer_placeholder.ps1
```
