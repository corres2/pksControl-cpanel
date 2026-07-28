# Deploy en cPanel Python App

Guia para preparar una copia recortada futura del proyecto `pksControl` para hosting cPanel con Python App. No reemplaza el despliegue Docker actual.

## Datos confirmados del proyecto

- `DJANGO_SETTINGS_MODULE`: `config.settings.prod`.
- `manage.py`: `app/manage.py`.
- WSGI Django real: `app/config/wsgi.py`.
- WSGI para cPanel: `passenger_wsgi.py` en la raiz del proyecto.
- Dependencias de produccion: `requirements.txt`, que apunta a `requirements/prod.txt`.
- Static root: `app/staticfiles`.
- Media root: `app/media`.

## Requisitos del hosting

- cPanel con soporte para Setup Python App / Passenger.
- Python recomendado: 3.12 si el hosting lo ofrece. Alternativa: 3.11 si 3.12 no esta disponible y las dependencias instalan correctamente.
- MySQL disponible desde cPanel.
- Acceso a terminal o consola para ejecutar `pip`, `python app/manage.py migrate` y `collectstatic`.
- Compilacion de `mysqlclient` soportada por el hosting, o paquete equivalente ya disponible por el proveedor.

## Crear Python App

1. Entrar a cPanel > Setup Python App.
2. Crear una app nueva con Python 3.12 recomendado.
3. Definir Application root apuntando a la raiz donde se suba el proyecto.
4. Definir Application URL segun el dominio o subdominio asignado.
5. Usar `passenger_wsgi.py` como archivo WSGI.
6. Reiniciar la app desde cPanel despues de instalar dependencias y configurar variables.

## Base MySQL en cPanel

1. Crear base de datos MySQL desde cPanel.
2. Crear usuario MySQL.
3. Asignar permisos del usuario a la base.
4. Guardar hostname, puerto, base, usuario y password para el `.env` del servidor.

## Variables de entorno

Crear un `.env` en la raiz del proyecto dentro del hosting. No subir el `.env` real a Git ni al ZIP.

Variables esperadas:

```text
DJANGO_SECRET_KEY=valor-seguro
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=midominio.com,www.midominio.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://midominio.com,https://www.midominio.com
TIME_ZONE=America/Mexico_City
MYSQL_DATABASE=nombre_base_cpanel
MYSQL_USER=usuario_cpanel
MYSQL_PASSWORD=password_cpanel
DB_HOST=localhost
DB_PORT=3306
APP_VERSION=0.1.0
SERVER_NAME=cpanel
```

Usar el host MySQL indicado por cPanel si no es `localhost`.

## Instalacion

Desde la terminal de cPanel, dentro del entorno virtual de la Python App:

```bash
pip install -r requirements.txt
python app/manage.py check
python app/manage.py migrate
python app/manage.py collectstatic --noinput
```

Despues reiniciar la Python App desde cPanel.

## Verificacion

- Abrir la URL configurada en cPanel.
- Revisar `/accounts/login/`.
- Iniciar sesion con un usuario creado previamente o crear superusuario si aplica:

```bash
python app/manage.py createsuperuser
```

## Troubleshooting

- Error `No module named config`: confirmar que `passenger_wsgi.py` esta en la raiz y agrega `app/` al `sys.path`.
- Error de MySQL: revisar `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `DB_HOST` y permisos del usuario.
- Error de `mysqlclient`: pedir al hosting soporte para compilar extensiones Python/MySQL o instalar librerias del sistema requeridas.
- Error 500 despues de subir cambios: revisar logs de la Python App en cPanel y reiniciar la app.
- Static files no visibles: ejecutar `python app/manage.py collectstatic --noinput` y confirmar que cPanel sirve `app/staticfiles`.
- CSRF/host bloqueado: ajustar `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS`.
