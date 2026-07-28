from collections import defaultdict
from decimal import Decimal

from apps.conceptos.models import (
    HistorialCoincidencia,
    PatronSerie,
    normalizar_texto,
)


MIN_SERIES_UNICAS = 3
MIN_PREFIX_LEN = 3


def analizar_historial_para_propuestas(min_series=MIN_SERIES_UNICAS, min_prefix_len=MIN_PREFIX_LEN):
    evidencias = HistorialCoincidencia.objects.filter(
        usar_para_biblioteca=True,
    ).exclude(
        serie='',
    ).exclude(
        numero_parte='',
    )
    grupos = defaultdict(list)
    for evidencia in evidencias:
        firma = _firma_evidencia(evidencia)
        grupos[_firma_key(firma)].append(evidencia)

    patrones = []
    for firma_key, elementos in grupos.items():
        firma = _firma_desde_key(firma_key)
        patron = _crear_o_actualizar_patron(firma, elementos, min_series, min_prefix_len)
        if patron:
            patrones.append(patron)
    return patrones

def _crear_o_actualizar_patron(firma, evidencias, min_series, min_prefix_len):
    series_unicas = sorted({normalizar_texto(evidencia.serie) for evidencia in evidencias if evidencia.serie})
    numero_partes = sorted({normalizar_texto(evidencia.numero_parte) for evidencia in evidencias if evidencia.numero_parte})
    modelo = firma['modelo']
    descripcion = firma['descripcion']
    numero_parte = firma['numero_parte']
    sample_size = len(series_unicas)
    evidencias_totales = len(evidencias)
    motivo = ''
    estado = PatronSerie.ESTADO_OBSERVADO
    prefix = _prefijo_comun(series_unicas)

    if sample_size >= min_series and (not prefix or len(prefix) < min_prefix_len):
        motivo = 'prefijo demasiado corto'
        estado = PatronSerie.ESTADO_CONFLICTO
    elif sample_size >= min_series and len(numero_partes) > 1:
        motivo = 'misma serie o prefijo asociado a varios numero_parte'
        estado = PatronSerie.ESTADO_CONFLICTO
    elif sample_size >= min_series and _prefijo_tiene_conflicto(prefix, numero_parte):
        motivo = 'mismo prefijo asociado a varios numero_parte'
        estado = PatronSerie.ESTADO_CONFLICTO
    elif sample_size >= min_series:
        estado = PatronSerie.ESTADO_APROBADO
    elif sample_size == 2:
        estado = PatronSerie.ESTADO_EN_CRECIMIENTO

    confidence = Decimal('0') if estado == PatronSerie.ESTADO_CONFLICTO else _confidence(sample_size)
    patron = _buscar_patron_compatible(prefix, numero_parte, firma)
    defaults = {
        'numero_parte': numero_parte,
        'modelo': modelo,
        'descripcion': descripcion,
        'firma_json': firma,
        'firma_texto': _firma_texto(firma),
        'sample_size': sample_size,
        'min_required': min_series,
        'confidence': confidence,
        'activo': estado == PatronSerie.ESTADO_APROBADO,
        'source': 'evidence_autoapproved' if estado == PatronSerie.ESTADO_APROBADO else 'historial_coincidencia',
        'estado': estado,
        'evidencias_totales': evidencias_totales,
        'series_unicas': sample_size,
        'motivo_conflicto': motivo,
    }
    if patron:
        for campo, valor in defaults.items():
            setattr(patron, campo, valor)
        patron.save(update_fields=[*defaults.keys(), 'updated_at'])
        return patron
    return PatronSerie.objects.create(
        campo_identificador=PatronSerie.CAMPO_SERIE,
        prefix=prefix,
        **defaults,
    )


def _firma_evidencia(evidencia):
    return {
        'numero_parte': normalizar_texto(evidencia.numero_parte),
        'modelo': normalizar_texto(evidencia.modelo),
        'descripcion': normalizar_texto(evidencia.descripcion),
    }


def _firma_key(firma):
    return (
        firma['numero_parte'],
        firma['modelo'],
        firma['descripcion'],
    )


def _firma_desde_key(firma_key):
    return {
        'numero_parte': firma_key[0],
        'modelo': firma_key[1],
        'descripcion': firma_key[2],
    }


def _prefijo_comun(series):
    if not series:
        return ''
    prefix = series[0]
    for serie in series[1:]:
        while not serie.startswith(prefix) and prefix:
            prefix = prefix[:-1]
    return prefix


def _confidence(sample_size):
    if sample_size >= 10:
        return Decimal('0.9500')
    if sample_size >= 6:
        return Decimal('0.9000')
    if sample_size >= 4:
        return Decimal('0.7500')
    return Decimal('0.6000')


def _prefijo_tiene_conflicto(prefix, numero_parte):
    return PatronSerie.objects.filter(
        prefix=prefix,
    ).exclude(
        numero_parte=numero_parte,
    ).exclude(
        estado=PatronSerie.ESTADO_RECHAZADO,
    ).exists()


def _firma_texto(firma_json):
    return '|'.join(f'{clave}={valor}' for clave, valor in firma_json.items())


def _buscar_patron_compatible(prefix, numero_parte, firma):
    for patron in PatronSerie.objects.filter(prefix=prefix, numero_parte=numero_parte):
        if not patron.firma_json or patron.firma_json == firma:
            return patron
    return None
