# RELEASE_COMMANDS_READY

## Contexto
Entorno actual sin `gh`; dejar comandos listos para ejecutar en estación con GitHub CLI autenticado.

## Opción A: Crear release estable `v1.0.0` desde RC4
```bash
gh auth status
gh release view v1.0.0-rc4

# (opcional) descargar asset RC4 para verificar hash local
mkdir -p out/release_assets
cd out/release_assets
gh release download v1.0.0-rc4 -p "ARIS_CONTROL_2.exe"
sha256sum ARIS_CONTROL_2.exe
# validar contra B9F6358E37F8ADCA1D4A78F4AF515FF15E3B50680EEBF24D17BC20238B2EEAA9

# crear GA usando el mismo asset (si la política del repo lo permite)
gh release create v1.0.0 ARIS_CONTROL_2.exe \
  --title "ARIS_CONTROL_2 v1.0.0" \
  --notes-file ARIS_CONTROL_2/out/release/release_notes_v1.0.0.md \
  --latest
```

## Opción B: Editar RC4 y quitar pre-release
```bash
gh auth status
gh release edit v1.0.0-rc4 \
  --prerelease=false \
  --title "ARIS_CONTROL_2 v1.0.0" \
  --latest
```

## Verificación posterior obligatoria (GitHub)
```bash
gh release view v1.0.0 --json tagName,isPrerelease,isDraft,name,assets,url
# o, si se mantuvo el tag RC4:
gh release view v1.0.0-rc4 --json tagName,isPrerelease,isDraft,name,assets,url
```

Checklist post-promoción:
1. Tag final correcto (`v1.0.0` o política vigente).
2. `isPrerelease=false`.
3. Asset `ARIS_CONTROL_2.exe` visible y descargable.
4. Notas de release publicadas.
5. URL del release compartida al equipo operativo.
