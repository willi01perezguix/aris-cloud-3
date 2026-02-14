# ARIS_CONTROL_2 — v1.0.1 Commands Ready

## Estado
- **Ejecución:** Pendiente por gate inicial FAIL.

## Comandos a ejecutar tras desbloqueo
```bash
pytest -q
```

```bash
# Smoke/regresión oficial (reemplazar por script oficial del repo si aplica)
# ./scripts/smoke.sh
```

```bash
# Build .exe (usar flujo oficial del repo)
# <comando_oficial_build_windows>
```

```bash
# SHA256 del artefacto
sha256sum <ruta_binario.exe>
```

```bash
# RC prerelease
# gh release create v1.0.1-rc1 <ruta_binario.exe> <ruta_checksum> --prerelease --title "v1.0.1-rc1" --notes-file docs/release/V1_0_1_RELEASE_NOTES.md
```

```bash
# Stable release (solo con GO final)
# gh release create v1.0.1 <ruta_binario.exe> <ruta_checksum> --title "v1.0.1" --notes-file docs/release/V1_0_1_RELEASE_NOTES.md
```
