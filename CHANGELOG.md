# Changelog

## Sin publicar

- CI en GitHub Actions (ruff + pytest con MySQL) y configuración de pre-commit.
- pytest corre desde la raíz; ruff con límite de 120 columnas y sin hallazgos.
- Tests de inicio actualizados al nombre "Catálogo Carta Porte".
- `CLAUDE.md` con convenciones y comandos del proyecto.
- Biblioteca de series: la colisión de prefijos solo se marca cuando un prefijo contiene al otro, y la
  descripción ya no separa grupos del mismo número de parte y modelo (los patrones aprobados dejaban de activarse).
- Comando `recalcular_patrones` para regenerar la biblioteca después del deploy.

## 0.1.1

- Se agregan scripts PowerShell para Windows 11.
- Se actualiza README y MANUAL con flujo Windows 11 Home + Docker Desktop + WSL 2.
- Se ajustan respaldos para generarse desde el contenedor MySQL hacia `backups/`.

## 0.1.0

- Base inicial Django + Docker + MySQL + Nginx.
- Scripts Linux/macOS para instalación, actualización, respaldo y healthcheck.
