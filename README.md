# pksControl - Versión cPanel

Versión preparada para despliegue en hosting cPanel con Python App.

Este repositorio contiene solo los archivos necesarios para ejecutar la aplicación Django en cPanel, sin Docker, sin Docker Compose y sin servicios locales como Nginx o phpMyAdmin en contenedor.

## Objetivo

Permitir la instalación de pksControl en un hosting cPanel que soporte aplicaciones Python, usando una base MySQL creada desde cPanel y dependencias de producción.

## Estructura principal

```txt
pksControl-cpanel/
├── app/                    Código fuente Django
├── docs/                   Documentación de despliegue cPanel
├── requirements/           Dependencias por ambiente
├── passenger_wsgi.py       Entrada WSGI para cPanel / Passenger
├── requirements.txt        Dependencias de producción
├── .env.example            Plantilla de configuración
└── README.md               Guía rápida