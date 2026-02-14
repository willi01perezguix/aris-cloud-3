# 03 — Release Runbook (v1.0.0)

## 1) Flujo release candidate -> stable
1. Ejecutar `preflight_release.ps1` en rama objetivo.
2. Ejecutar `smoke_release.ps1` para pruebas mínimas + build.
3. Generar notas base con `package_release_notes.ps1`.
4. Validar UAT final y evidencias en `out/uat`.
5. Crear tag `v1.0.0` y publicar release estable.

## 2) Checklist pre-release
- Rama correcta y working tree limpio.
- `.env.example` presente y actualizado.
- `.env` ignorado por git.
- Entrypoint detectable.
- `pytest -q` en verde.
- Script de run y build presentes.
- `dist/ARIS_CONTROL_2.exe` generado.

## 3) Generar hash SHA256 del exe
```powershell
Get-FileHash .\dist\ARIS_CONTROL_2.exe -Algorithm SHA256
```
Registrar hash en notas de release y evidencia UAT.

## 4) Publicar release en GitHub con assets
1. Empujar commits y tag:
   ```powershell
   git push origin <branch>
   git tag v1.0.0
   git push origin v1.0.0
   ```
2. En GitHub Releases:
   - Seleccionar tag `v1.0.0`.
   - Título: `ARIS_CONTROL_2 v1.0.0`.
   - Pegar contenido de `out/release/release_notes_v1.0.0.md`.
   - Adjuntar `dist/ARIS_CONTROL_2.exe`.

## 5) Rollback básico
```powershell
git checkout <tag-previo-estable>
```
Si aplica despliegue asociado, reinstalar binario del tag anterior y volver a verificar smoke.

## 6) Post-release verification
- Ejecutar binario en host Windows limpio.
- Validar login + `/me` + admin core + export CSV.
- Confirmar hash del asset publicado.
- Registrar incidencias con `trace_id`.
