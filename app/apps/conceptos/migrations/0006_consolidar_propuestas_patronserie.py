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


def estado_desde_propuesta(estado):
    return {
        'pendiente': 'pendiente',
        'aprobada': 'aprobado',
        'rechazada': 'rechazado',
        'conflicto': 'conflicto',
    }.get(estado, 'pendiente')


def activo_desde_estado(estado):
    return estado == 'aprobado'


def consolidar_patrones(apps, schema_editor):
    PatronSerie = apps.get_model('conceptos', 'PatronSerie')
    PropuestaPatronSerie = apps.get_model('conceptos', 'PropuestaPatronSerie')

    for patron in PatronSerie.objects.all():
        patron.estado = 'aprobado'
        patron.evidencias_totales = patron.sample_size
        patron.series_unicas = patron.sample_size
        patron.save(
            update_fields=[
                'estado',
                'evidencias_totales',
                'series_unicas',
                'updated_at',
            ]
        )

    patrones = list(PatronSerie.objects.all())
    for propuesta in PropuestaPatronSerie.objects.order_by('created_at', 'id'):
        compatible = next(
            (patron for patron in patrones if patron_compatible(patron, propuesta)),
            None,
        )

        if compatible:
            campos = []
            if not compatible.revisado_por_id and propuesta.revisado_por_id:
                compatible.revisado_por_id = propuesta.revisado_por_id
                campos.append('revisado_por')
            if not compatible.revisado_at and propuesta.revisado_at:
                compatible.revisado_at = propuesta.revisado_at
                campos.append('revisado_at')
            if not compatible.motivo_conflicto and propuesta.motivo_conflicto:
                compatible.motivo_conflicto = propuesta.motivo_conflicto
                campos.append('motivo_conflicto')

            if compatible.estado != 'aprobado':
                nuevo_estado = estado_desde_propuesta(propuesta.estado)
                compatible.estado = nuevo_estado
                compatible.activo = activo_desde_estado(nuevo_estado)
                campos.extend(['estado', 'activo'])

            if propuesta.sample_size > compatible.sample_size:
                compatible.sample_size = propuesta.sample_size
                compatible.evidencias_totales = propuesta.sample_size
                compatible.series_unicas = propuesta.sample_size
                campos.extend(['sample_size', 'evidencias_totales', 'series_unicas'])

            if campos:
                compatible.save(update_fields=[*set(campos), 'updated_at'])
            continue

        nuevo_estado = estado_desde_propuesta(propuesta.estado)
        nuevo_patron = PatronSerie.objects.create(
            campo_identificador='serie',
            prefix=normalizar_prefix(propuesta.prefix),
            numero_parte=normalizar_texto(propuesta.numero_parte),
            modelo=normalizar_texto(propuesta.modelo),
            descripcion=propuesta.descripcion,
            firma_json=propuesta.firma_json,
            firma_texto='',
            sample_size=propuesta.sample_size,
            min_required=3,
            confidence=propuesta.confidence,
            activo=activo_desde_estado(nuevo_estado),
            source=propuesta.source,
            estado=nuevo_estado,
            evidencias_totales=propuesta.sample_size,
            series_unicas=propuesta.sample_size,
            motivo_conflicto=propuesta.motivo_conflicto,
            revisado_por_id=propuesta.revisado_por_id,
            revisado_at=propuesta.revisado_at,
        )
        patrones.append(nuevo_patron)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('conceptos', '0005_patronserie_unificacion_campos'),
    ]

    operations = [
        migrations.RunPython(consolidar_patrones, noop_reverse),
    ]
