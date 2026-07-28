# Archivos para repo/ZIP cPanel

Guia para preparar una copia futura recortada del proyecto en un repo separado, por ejemplo `pksControl-cpanel`.

## Incluir

- `app/`
- `requirements/`
- `requirements.txt`
- `passenger_wsgi.py`
- `.env.example`
- `.cpanelignore`
- `README.md`
- `CHANGELOG.md` si se desea historial de version.
- `MANUAL.md` si aplica para usuarios finales.
- `docs/CPANEL_DEPLOY.md`
- `docs/CPANEL_ZIP_INCLUDE.md`
- Migraciones Django dentro de cada app.

## No incluir

- `.env` real.
- `.env.*` reales con secretos.
- `.git/`
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
- `app/media/` con archivos reales de usuarios, salvo que se haga una migracion controlada.
- `app/staticfiles/` generado, salvo que el hosting no permita ejecutar `collectstatic`.

## Advertencias

- No incluir nunca el `.env` real en Git, ZIP ni tickets de soporte.
- No usar `requirements/dev.txt` en produccion.
- Usar `requirements.txt`, que debe apuntar a dependencias de produccion.
- No mezclar este paquete cPanel con archivos Docker del repo principal.
- Validar que `DJANGO_DEBUG=False` antes de publicar.
- Confirmar que `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` correspondan al dominio real.
