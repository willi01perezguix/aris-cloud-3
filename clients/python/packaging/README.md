# Windows Packaging Scaffold

## Prerequisites
- Python 3.11+
- Visual C++ Redistributable
- `pip install pyinstaller`

## Setup
```powershell
cd clients/python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
```

## Build commands
```powershell
cd packaging
./build_core.ps1
./build_control_center.ps1
```

Batch alternatives:
```cmd
build_core.bat
build_control_center.bat
```

## Outputs
- `clients/python/packaging/dist/ARIS-CORE-3`
- `clients/python/packaging/dist/ARIS-Control-Center`

## Troubleshooting
- Missing DLL: add explicit binary/data in spec template.
- Hidden imports: append modules to `hiddenimports` in the spec template.
- Antivirus false positives: sign binaries and use reproducible clean build machine.
