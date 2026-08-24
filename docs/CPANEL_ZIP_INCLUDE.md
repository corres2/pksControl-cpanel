# Archivos para repo/ZIP cPanel

Guia para preparar una copia recortada del proyecto para cPanel. El repositorio Git puede conservar documentación y tests; el paquete de despliegue debe contener solo archivos necesarios para ejecutar la aplicación.

## Incluir

- `app/`
- `requirements/`
- `requirements.txt`
- `passenger_wsgi.py`
- Migraciones Django dentro de cada app.

La documentación, `.env.example` y archivos de control del repositorio no se incluyen en el paquete final; se conservan en Git para referencia y operación segura.

## No incluir

- `.env` real.
- `.env.*` reales con secretos.
- `.git/`
- `.gitignore`
- `.cpanelignore`
- `README.md`
- `AGENTS.md`
- `docs/`
- `tests.py` y carpetas `tests/`
- `.agents/`
- `.codex/`
- `docker/`
- `docker-compose.yml`
- `scripts/` si son solo operativos Docker/local.
- `backups/`
- `logs/`
- `mysql_data/`
- `venv/`
- `__pycache__/`
- `*.pyc`
- `*.pyo`, `*.pyd`
- `*.tmp`, `*.bak`, `~$*`, `*.zip`
- `.env.example`
- `app/media/` con archivos reales de usuarios, salvo que se haga una migracion controlada.
- `app/staticfiles/` generado se conserva solo si el hosting lo requiere; de lo contrario, ejecutar `collectstatic` en cPanel.

## Advertencias

- No incluir nunca el `.env` real en Git, ZIP ni tickets de soporte.
- No usar `requirements/dev.txt` en produccion.
- Usar `requirements.txt`, que debe apuntar a dependencias de produccion.
- No mezclar este paquete cPanel con archivos Docker del repo principal.
- Validar que `DJANGO_DEBUG=False` antes de publicar.
- Confirmar que `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` correspondan al dominio real.
