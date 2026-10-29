# pksControl

App interna Django + MySQL para capturar facturas de mercancía (número de parte, serie, modelo,
cantidad, precio) con biblioteca de patrones serie → número de parte, y catálogos de números de
parte y claves SAT/Carta Porte. Se despliega en **cPanel (Passenger)**, sin Docker.

## Estructura

- `app/config/settings/{base,dev,prod}.py`: config por ambiente; todo sale de `.env` (django-environ).
- `app/apps/conceptos/`: facturas (`DocumentoConceptos`, `Concepto`), importación CSV/XLSX,
  historial (`HistorialCoincidencia`) y patrones (`PatronSerie`, lógica en `services.py`).
- `app/apps/catalogos/`: `NumeroParte`, `ClaveProductoServicioSAT`, bitácora `CargaCatalogo`;
  importación en `services/importacion.py`.
- `app/apps/core/`: inicio y estado del sistema.
- `app/templates/`: plantillas; CSS en `base.html`. Guía de UI: `docs/UI_UX_GUIDE.md`.
- `passenger_wsgi.py` + `requirements.txt` (→ `requirements/prod.txt`): entrada de cPanel. No romper.

## Comandos (entorno local Docker)

`docker-compose.yml` y `docker/` son solo locales (excluidos en `.git/info/exclude` y en
`.cpanelignore`). Web en http://localhost:8010, MySQL en el puerto 3308.

```bash
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web sh -c "cd /code && pytest -q"                 # toda la suite
docker compose exec web sh -c "cd /code && pytest -q app/apps/conceptos/tests.py -k confirmar"
docker compose exec web sh -c "cd /code && ruff check app"
docker compose exec web python manage.py makemigrations --check --dry-run
```

## Convenciones

- Código, modelos, vistas y mensajes en **español**; comillas simples; máximo 120 columnas (ruff).
- Vistas con función + `@permission_required` (usar permisos propios del modelo en `Meta.permissions`)
  y `@require_POST` en toda acción que cambie datos.
- Reglas de negocio en `services`/modelos, no en vistas. Estados de factura:
  borrador → confirmado → cancelado; solo un borrador se edita.
- Importaciones: siempre analizar → preview → confirmar; nunca guardar sin preview.
- Tests en `tests.py` de cada app (Django `TestCase`, MySQL real). Una regla nueva o un bug
  corregido lleva su test.
- Migraciones: una por cambio de modelo, con nombre descriptivo; revisar que `makemigrations --check` quede limpio.

## Flujo de trabajo

- Rama por tarea (`feat/…`, `fix/…`, `chore/…`), commits chicos con prefijo
  (`feat:`, `fix:`, `ui:`, `chore:`, `test:`), PR a `main`. La CI (ruff + pytest) debe pasar.
- Antes de cerrar una tarea: `ruff check app` y los tests de la app tocada.
- Cambios de deploy (settings prod, requirements, `passenger_wsgi.py`): actualizar `docs/CPANEL_DEPLOY.md`
  y `CHANGELOG.md`.
- No agregar Docker ni servicios al repo: la versión de producción es cPanel.
