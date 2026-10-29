from collections import OrderedDict
from decimal import Decimal

from django.db.models.functions import Upper
from django.utils import timezone

from apps.conceptos.models import Concepto, DocumentoConceptos

# Un costo se alerta cuando supera en mas de 20% al minimo historico del numero de parte.
UMBRAL_ALERTA = Decimal('0.20')


def usos_confirmados():
    return Concepto.objects.filter(
        documento__status=DocumentoConceptos.STATUS_CONFIRMADO,
        precio_unitario__gt=0,
    ).exclude(numero_parte='').annotate(numero_parte_normalizado=Upper('numero_parte'))


def supera_umbral(precio, minimo):
    return minimo is not None and minimo > 0 and precio > minimo * (1 + UMBRAL_ALERTA)


def variacion_porcentual(precio, minimo):
    if not minimo:
        return None
    return ((precio - minimo) / minimo * 100).quantize(Decimal('0.1'))


def resumen_costos(q='', solo_alertas=False):
    usos = usos_confirmados()
    if q:
        usos = usos.filter(numero_parte_normalizado__contains=q.strip().upper())
    filas = OrderedDict()
    registros = usos.order_by('numero_parte_normalizado', 'documento__created_at', 'id').values_list(
        'numero_parte_normalizado',
        'precio_unitario',
        'documento__created_at',
    )
    for numero_parte, precio, fecha in registros.iterator(chunk_size=2000):
        fila = filas.get(numero_parte)
        if fila is None:
            fila = filas[numero_parte] = {
                'numero_parte': numero_parte,
                'usos': 0,
                'minimo': precio,
                'fecha_minimo': fecha,
                'maximo': precio,
                'primer_uso': fecha,
            }
        fila['usos'] += 1
        if precio <= fila['minimo']:
            fila['minimo'] = precio
            fila['fecha_minimo'] = fecha
        fila['maximo'] = max(fila['maximo'], precio)
        fila['ultimo_precio'] = precio
        fila['ultimo_uso'] = fecha

    resultado = []
    for fila in filas.values():
        fila['variacion'] = variacion_porcentual(fila['ultimo_precio'], fila['minimo'])
        fila['alerta'] = supera_umbral(fila['ultimo_precio'], fila['minimo'])
        if solo_alertas and not fila['alerta']:
            continue
        resultado.append(fila)
    return resultado


def bitacora_costos(numero_parte):
    usos = usos_confirmados().filter(
        numero_parte_normalizado=numero_parte.strip().upper(),
    ).select_related('documento').order_by('documento__created_at', 'id')
    bitacora = []
    minimo_previo = None
    for concepto in usos:
        precio = concepto.precio_unitario
        bitacora.append({
            'concepto': concepto,
            'documento': concepto.documento,
            'fecha': concepto.documento.created_at,
            'precio': precio,
            'minimo_previo': minimo_previo,
            'variacion': variacion_porcentual(precio, minimo_previo),
            'alerta': supera_umbral(precio, minimo_previo),
            'nuevo_minimo': minimo_previo is None or precio < minimo_previo,
        })
        minimo_previo = precio if minimo_previo is None else min(minimo_previo, precio)
    return bitacora


def evaluar_costo(numero_parte, precio, excluir_documento=None):
    """Compara un precio contra el minimo historico confirmado; None si no hay historial."""
    numero_parte = (numero_parte or '').strip().upper()
    if not numero_parte or precio is None or precio <= 0:
        return None
    usos = usos_confirmados().filter(numero_parte_normalizado=numero_parte)
    if excluir_documento is not None:
        usos = usos.exclude(documento=excluir_documento)
    minimo = usos.order_by('precio_unitario', '-documento__created_at', '-id').select_related('documento').first()
    if minimo is None:
        return None
    return {
        'numero_parte': numero_parte,
        'minimo': minimo.precio_unitario,
        'fecha_minimo': minimo.documento.created_at,
        'folio_minimo': minimo.documento.folio,
        'variacion': variacion_porcentual(precio, minimo.precio_unitario),
        'alerta': supera_umbral(precio, minimo.precio_unitario),
    }


def alerta_costo_para_sesion(numero_parte, precio):
    """Version serializable (JSON) de evaluar_costo, solo cuando hay alerta."""
    evaluacion = evaluar_costo(numero_parte, precio)
    if not evaluacion or not evaluacion['alerta']:
        return None
    return {
        'minimo': str(evaluacion['minimo']),
        'fecha_minimo': timezone.localtime(evaluacion['fecha_minimo']).strftime('%Y-%m-%d'),
        'folio_minimo': evaluacion['folio_minimo'],
        'variacion': str(evaluacion['variacion']),
    }


def mensaje_alerta_costo(evaluacion):
    fecha = timezone.localtime(evaluacion['fecha_minimo']).strftime('%Y-%m-%d')
    return (
        f'Alerta de costo: {evaluacion["numero_parte"]} está {evaluacion["variacion"]}% arriba del mínimo '
        f'histórico ({evaluacion["minimo"]:.2f} en {evaluacion["folio_minimo"]}, {fecha}).'
    )
