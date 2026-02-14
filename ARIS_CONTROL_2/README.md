# ARIS_CONTROL_2

Cliente operativo para ARIS Cloud 3 enfocado en login, contexto `/me`, administración (tenants/stores/users), filtros, paginación y exportación CSV.

## Quickstart

### Opción A: PowerShell local (sin `.venv`)
```powershell
cd ARIS_CONTROL_2
python -m pip install --upgrade pip
pip install -e .[dev]
```

### Opción B: PowerShell con `.venv`
```powershell
cd ARIS_CONTROL_2
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
```

## Configuración por defecto
Copiar `.env.example` a `.env`:
```powershell
Copy-Item .env.example .env
```

Valores por defecto:
- `ARIS3_BASE_URL=https://aris-cloud-3-api-pecul.ondigitalocean.app/`
- `ARIS3_TIMEOUT_SECONDS=30`
- `ARIS3_VERIFY_SSL=true`

> `.env` está excluido de git. `.env.example` sí se versiona.

## Ejecución
```powershell
.\scripts\windows\run_control_center_dev.ps1
```

## Export CSV
Los CSV operativos se guardan bajo:
- `out/exports/`

## Empaquetado Windows
```powershell
.\scripts\windows\build_control_center.ps1
```
Resultado esperado:
- `dist/ARIS_CONTROL_2.exe`

## Flujo release/hardening
```powershell
.\scripts\windows\preflight_release.ps1
.\scripts\windows\smoke_release.ps1
.\scripts\windows\package_release_notes.ps1
Get-FileHash .\dist\ARIS_CONTROL_2.exe -Algorithm SHA256
```

## Documentación operativa
- [Manual Operativo](docs/01_MANUAL_OPERATIVO.md)
- [UAT Final Checklist](docs/02_UAT_FINAL_CHECKLIST.md)
- [Release Runbook](docs/03_RELEASE_RUNBOOK.md)
- [Operación Diaria](docs/04_OPERACION_DIARIA.md)
