import re

from django.db import migrations


def normalizar_texto(valor):
    return re.sub(r'\s+', ' ', (valor or '').strip()).upper()


def normalizar_prefix(valor):
    return (valor or '').strip().upper()


def normalizar_firma(firma_json, firma_texto=''):
    if firma_json:
        return tuple(sorted((str(clave), str(valor)) for clave, valor in firma_json.items()))
    return (firma_texto or '').strip().upper()


def patron_compatible(patron, propuesta):
    if normalizar_prefix(patron.prefix) != normalizar_prefix(propuesta.prefix):
        return False
    if normalizar_texto(patron.numero_parte) != normalizar_texto(propuesta.numero_parte):
        return False

    firma_propuesta = normalizar_firma(propuesta.firma_json, '')
    firma_patron = normalizar_firma(patron.firma_json, getattr(patron, 'firma_texto', ''))
    if firma_propuesta and firma_patron:
        return firma_propuesta == firma_patron
    return True


def validar_propuestas_consolidadas(apps, schema_editor):
    PatronSerie = apps.get_model('conceptos', 'PatronSerie')
    PropuestaPatronSerie = apps.get_model('conceptos', 'PropuestaPatronSerie')
    patrones = list(PatronSerie.objects.all())
    faltantes = []

    for propuesta in PropuestaPatronSerie.objects.all():
        if not any(patron_compatible(patron, propuesta) for patron in patrones):
            faltantes.append(f'{propuesta.prefix} -> {propuesta.numero_parte}')

    if faltantes:
        ejemplos = ', '.join(faltantes[:10])
        raise RuntimeError(
            'No se puede eliminar PropuestaPatronSerie; hay propuestas sin PatronSerie '
            f'compatible consolidado: {ejemplos}'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('conceptos', '0006_consolidar_propuestas_patronserie'),
    ]

    operations = [
        migrations.RunPython(validar_propuestas_consolidadas, migrations.RunPython.noop),
        migrations.DeleteModel(
            name='PropuestaPatronSerie',
        ),
    ]
