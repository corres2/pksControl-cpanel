import json

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalogos.models import NumeroParte
from apps.conceptos.exportacion import exportar_documento_conceptos_docx
from apps.conceptos.forms import ConceptoForm, DocumentoConceptosForm
from apps.conceptos.importacion import (
    analizar_archivo_conceptos,
    confirmar_importacion_conceptos,
)
from apps.conceptos.services import analizar_historial_para_propuestas
from apps.conceptos.models import (
    Concepto,
    DocumentoConceptos,
    HistorialCoincidencia,
    PatronSerie,
    registrar_historial_concepto,
)


ACCION_BUSCAR_NUMERO_PARTE = 'buscar_numero_parte'
ACCION_BUSCAR_SERIE = 'buscar_serie'
ACCION_BUSCAR_HISTORIAL = 'buscar_historial'
ACCION_USAR_SUGERENCIA = 'usar_sugerencia'
SESSION_IMPORTACION_PREFIX = 'conceptos_importacion_'


@permission_required('conceptos.view_documentoconceptos')
def documentos_list(request):
    queryset = DocumentoConceptos.objects.select_related('usuario').order_by('-created_at')
    busqueda = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    fuente = request.GET.get('fuente', '').strip()
    estados_validos = {valor for valor, _ in DocumentoConceptos.STATUSES}
    fuentes_validas = {valor for valor, _ in DocumentoConceptos.FUENTES}
    if busqueda:
        queryset = queryset.filter(folio__icontains=busqueda)
    if estado in estados_validos:
        queryset = queryset.filter(status=estado)
    else:
        estado = ''
    if fuente in fuentes_validas:
        queryset = queryset.filter(fuente=fuente)
    else:
        fuente = ''
    query_params = request.GET.copy()
    query_params.pop('page', None)
    filtros_activos = []
    if busqueda:
        filtros_activos.append(f'Folio: {busqueda}')
    if estado:
        filtros_activos.append(dict(DocumentoConceptos.STATUSES)[estado])
    if fuente:
        filtros_activos.append(dict(DocumentoConceptos.FUENTES)[fuente])
    page_obj = Paginator(queryset, 25).get_page(request.GET.get('page'))
    return render(
        request,
        (
            'conceptos/partials/documentos_resultados.html'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            else 'conceptos/documentos_list.html'
        ),
        {
            'page_obj': page_obj,
            'busqueda': busqueda,
            'estado': estado,
            'fuente': fuente,
            'status_choices': DocumentoConceptos.STATUSES,
            'fuente_choices': DocumentoConceptos.FUENTES,
            'filtros_activos': filtros_activos,
            'filtros_aplicados': bool(filtros_activos),
            'querystring': query_params.urlencode(),
        },
    )


@permission_required('conceptos.add_documentoconceptos')
def documento_create(request):
    form = DocumentoConceptosForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        documento = form.save(commit=False)
        documento.usuario = request.user if request.user.is_authenticated else None
        documento.save()
        messages.success(request, 'Factura creada correctamente.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    return render(
        request,
        'conceptos/documento_form.html',
        {'form': form, 'titulo': 'Nueva factura'},
    )


@permission_required('conceptos.view_documentoconceptos')
def documento_detail(request, pk):
    documento = get_object_or_404(
        DocumentoConceptos.objects.select_related('usuario').prefetch_related('conceptos'),
        pk=pk,
    )
    return render(
        request,
        'conceptos/documento_detail.html',
        {'documento': documento},
    )


@permission_required('conceptos.view_documentoconceptos')
def documento_exportar_word(request, pk):
    documento = get_object_or_404(
        DocumentoConceptos.objects.select_related('usuario').prefetch_related('conceptos'),
        pk=pk,
    )
    return exportar_documento_conceptos_docx(documento)


@permission_required('conceptos.change_documentoconceptos')
def documento_update(request, pk):
    documento = get_object_or_404(DocumentoConceptos, pk=pk)
    if not documento.es_borrador:
        messages.error(request, 'Solo se pueden editar facturas en borrador.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    form = DocumentoConceptosForm(request.POST or None, instance=documento)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Factura actualizada correctamente.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    return render(
        request,
        'conceptos/documento_form.html',
        {'form': form, 'titulo': f'Editar {documento.folio}', 'documento': documento},
    )


@permission_required('conceptos.change_documentoconceptos')
def conceptos_importar(request, pk):
    documento = get_object_or_404(DocumentoConceptos, pk=pk)
    if not documento.es_borrador:
        messages.error(request, 'Solo se pueden importar conceptos en facturas en borrador.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    preview = None
    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if not archivo:
            messages.error(request, 'Selecciona un archivo CSV o XLSX.')
        else:
            try:
                preview = analizar_archivo_conceptos(archivo, documento=documento)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                request.session[_importacion_session_key(documento)] = preview
                request.session.modified = True

    return render(
        request,
        'conceptos/importar_conceptos.html',
        {'documento': documento, 'preview': preview},
    )


@require_POST
@permission_required('conceptos.change_documentoconceptos')
def conceptos_importar_confirmar(request, pk):
    documento = get_object_or_404(DocumentoConceptos, pk=pk)
    if not documento.es_borrador:
        messages.error(request, 'Solo se pueden importar conceptos en facturas en borrador.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    session_key = _importacion_session_key(documento)
    preview = request.session.get(session_key)
    if not preview:
        messages.error(request, 'No hay una importación pendiente por confirmar.')
        return redirect('conceptos:conceptos_importar', pk=documento.pk)
    if not preview['resumen']['validas']:
        messages.error(request, 'No hay filas válidas para importar.')
        return redirect('conceptos:conceptos_importar', pk=documento.pk)

    creados = confirmar_importacion_conceptos(
        documento,
        preview['filas'],
        usuario=request.user,
    )
    del request.session[session_key]
    request.session.modified = True
    messages.success(request, f'Conceptos de factura importados correctamente: {creados}.')
    return redirect('conceptos:documento_detail', pk=documento.pk)


@require_POST
@permission_required('conceptos.change_documentoconceptos')
def conceptos_importar_cancelar(request, pk):
    documento = get_object_or_404(DocumentoConceptos, pk=pk)
    if not documento.es_borrador:
        messages.error(request, 'Solo se puede cancelar una importación de una factura en borrador.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    session_key = _importacion_session_key(documento)
    if session_key in request.session:
        del request.session[session_key]
        request.session.modified = True
    messages.info(request, 'Importación cancelada. No se aplicaron cambios.')
    return redirect('conceptos:conceptos_importar', pk=documento.pk)


def _importacion_session_key(documento):
    return f'{SESSION_IMPORTACION_PREFIX}{documento.pk}'


@permission_required('conceptos.change_documentoconceptos')
def concepto_create(request, pk):
    documento = get_object_or_404(DocumentoConceptos, pk=pk)
    if not documento.es_borrador:
        messages.error(request, 'Solo se pueden agregar conceptos en una factura en borrador.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    form = ConceptoForm(request.POST or None, documento=documento)
    if request.method == 'POST' and request.POST.get('accion') == ACCION_BUSCAR_NUMERO_PARTE:
        form, sugerencias = _buscar_numero_parte_en_form(request, documento=documento)
        return render(
            request,
            'conceptos/concepto_form.html',
            {
                'form': form,
                'documento': documento,
                'titulo': 'Agregar concepto',
                'sugerencias': sugerencias,
            },
        )
    if request.method == 'POST' and request.POST.get('accion') == ACCION_BUSCAR_SERIE:
        form, sugerencias = _buscar_serie_en_form(request, documento=documento)
        return render(
            request,
            'conceptos/concepto_form.html',
            {
                'form': form,
                'documento': documento,
                'titulo': 'Agregar concepto',
                'sugerencias': sugerencias,
            },
        )
    if request.method == 'POST' and request.POST.get('accion') == ACCION_BUSCAR_HISTORIAL:
        form, sugerencias = _buscar_historial_en_form(request, documento=documento)
        return render(
            request,
            'conceptos/concepto_form.html',
            {
                'form': form,
                'documento': documento,
                'titulo': 'Agregar concepto',
                'sugerencias': sugerencias,
            },
        )
    if request.method == 'POST' and request.POST.get('accion') == ACCION_USAR_SUGERENCIA:
        form = _usar_sugerencia_en_form(request, documento=documento)
        return render(
            request,
            'conceptos/concepto_form.html',
            {'form': form, 'documento': documento, 'titulo': 'Agregar concepto'},
        )

    if request.method == 'POST' and form.is_valid():
        concepto = form.save(commit=False)
        concepto.documento = documento
        concepto.save()
        messages.success(request, 'Concepto agregado correctamente.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    return render(
        request,
        'conceptos/concepto_form.html',
        {'form': form, 'documento': documento, 'titulo': 'Agregar concepto'},
    )


@permission_required('conceptos.change_documentoconceptos')
def concepto_update(request, pk, concepto_id):
    documento = get_object_or_404(DocumentoConceptos, pk=pk)
    concepto = get_object_or_404(Concepto, pk=concepto_id, documento=documento)
    if not documento.es_borrador:
        messages.error(request, 'Solo se pueden editar conceptos en una factura en borrador.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    form = ConceptoForm(request.POST or None, instance=concepto, documento=documento)
    if request.method == 'POST' and request.POST.get('accion') == ACCION_BUSCAR_NUMERO_PARTE:
        form, sugerencias = _buscar_numero_parte_en_form(request, instance=concepto, documento=documento)
        return render(
            request,
            'conceptos/concepto_form.html',
            {
                'form': form,
                'documento': documento,
                'concepto': concepto,
                'titulo': 'Editar concepto',
                'sugerencias': sugerencias,
            },
        )
    if request.method == 'POST' and request.POST.get('accion') == ACCION_BUSCAR_SERIE:
        form, sugerencias = _buscar_serie_en_form(request, instance=concepto, documento=documento)
        return render(
            request,
            'conceptos/concepto_form.html',
            {
                'form': form,
                'documento': documento,
                'concepto': concepto,
                'titulo': 'Editar concepto',
                'sugerencias': sugerencias,
            },
        )
    if request.method == 'POST' and request.POST.get('accion') == ACCION_BUSCAR_HISTORIAL:
        form, sugerencias = _buscar_historial_en_form(request, instance=concepto, documento=documento)
        return render(
            request,
            'conceptos/concepto_form.html',
            {
                'form': form,
                'documento': documento,
                'concepto': concepto,
                'titulo': 'Editar concepto',
                'sugerencias': sugerencias,
            },
        )
    if request.method == 'POST' and request.POST.get('accion') == ACCION_USAR_SUGERENCIA:
        form = _usar_sugerencia_en_form(request, instance=concepto, documento=documento)
        return render(
            request,
            'conceptos/concepto_form.html',
            {'form': form, 'documento': documento, 'concepto': concepto, 'titulo': 'Editar concepto'},
        )

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Concepto actualizado correctamente.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    return render(
        request,
        'conceptos/concepto_form.html',
        {'form': form, 'documento': documento, 'concepto': concepto, 'titulo': 'Editar concepto'},
    )


@require_POST
@permission_required('conceptos.delete_documentoconceptos')
def concepto_delete(request, pk, concepto_id):
    documento = get_object_or_404(DocumentoConceptos, pk=pk)
    concepto = get_object_or_404(Concepto, pk=concepto_id, documento=documento)
    if not documento.es_borrador:
        messages.error(request, 'Solo se pueden quitar conceptos en una factura en borrador.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    concepto.delete()
    messages.success(request, 'Concepto eliminado correctamente.')
    return redirect('conceptos:documento_detail', pk=documento.pk)


@require_POST
@permission_required('conceptos.change_documentoconceptos', raise_exception=True)
def concepto_subir(request, pk, concepto_id):
    return _reordenar_concepto(request, pk, concepto_id, direccion='subir')


@require_POST
@permission_required('conceptos.change_documentoconceptos', raise_exception=True)
def concepto_bajar(request, pk, concepto_id):
    return _reordenar_concepto(request, pk, concepto_id, direccion='bajar')


@require_POST
@permission_required('conceptos.change_documentoconceptos', raise_exception=True)
def conceptos_reordenar(request, pk):
    documento = get_object_or_404(DocumentoConceptos, pk=pk)
    if documento.status != DocumentoConceptos.STATUS_BORRADOR:
        return JsonResponse(
            {'ok': False, 'error': 'Solo se pueden reordenar conceptos de una factura en borrador.'},
            status=400,
        )

    try:
        payload = json.loads(request.body.decode('utf-8'))
        orden = [int(concepto_id) for concepto_id in payload.get('orden', [])]
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'El orden recibido no es válido.'}, status=400)

    conceptos = list(documento.conceptos.order_by('orden', 'pk'))
    ids_actuales = {concepto.pk for concepto in conceptos}
    if len(orden) != len(ids_actuales) or set(orden) != ids_actuales:
        return JsonResponse(
            {'ok': False, 'error': 'El orden contiene conceptos inválidos para esta factura.'},
            status=400,
        )

    with transaction.atomic():
        for posicion, concepto_id in enumerate(orden, start=1):
            Concepto.objects.filter(pk=concepto_id, documento=documento).update(orden=posicion)

    return JsonResponse({'ok': True, 'orden': orden})


def _reordenar_concepto(request, pk, concepto_id, direccion):
    documento = get_object_or_404(DocumentoConceptos, pk=pk)
    concepto = get_object_or_404(Concepto, pk=concepto_id, documento=documento)
    es_ajax = _es_ajax(request)
    if documento.status == DocumentoConceptos.STATUS_CANCELADO:
        if es_ajax:
            return JsonResponse(
                {'ok': False, 'error': 'No se pueden reordenar conceptos de una factura cancelada.'},
                status=400,
            )
        messages.error(request, 'No se pueden reordenar conceptos de una factura cancelada.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    _normalizar_ordenes(documento)
    conceptos = list(documento.conceptos.order_by('orden', 'pk'))
    posicion = next(
        (index for index, item in enumerate(conceptos) if item.pk == concepto.pk),
        None,
    )
    if posicion is None:
        if es_ajax:
            return JsonResponse({'ok': False, 'error': 'Concepto no encontrado.'}, status=404)
        return redirect('conceptos:documento_detail', pk=documento.pk)

    destino = posicion - 1 if direccion == 'subir' else posicion + 1
    if destino < 0 or destino >= len(conceptos):
        if es_ajax:
            return JsonResponse(
                {'ok': False, 'error': 'El concepto ya esta en el limite del orden.'},
                status=400,
            )
        messages.warning(request, 'El concepto ya esta en el limite del orden.')
        return redirect('conceptos:documento_detail', pk=documento.pk)

    actual = conceptos[posicion]
    otro = conceptos[destino]
    Concepto.objects.filter(pk=actual.pk).update(orden=otro.orden)
    Concepto.objects.filter(pk=otro.pk).update(orden=actual.orden)
    if es_ajax:
        return JsonResponse(
            {
                'ok': True,
                'concepto_id': actual.pk,
                'accion': direccion,
            }
        )
    messages.success(request, 'Orden actualizado correctamente.')
    return redirect('conceptos:documento_detail', pk=documento.pk)


def _es_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _normalizar_ordenes(documento):
    conceptos = list(documento.conceptos.order_by('orden', 'pk'))
    for posicion, concepto in enumerate(conceptos, start=1):
        if concepto.orden != posicion:
            Concepto.objects.filter(pk=concepto.pk).update(orden=posicion)


def _buscar_numero_parte_en_form(request, instance=None, documento=None):
    datos = _datos_concepto_desde_post(request)
    encontrado = _aplicar_numero_parte_activo(request, datos, avisar_sin_numero=True)
    sugerencias = []
    if not encontrado and datos.get('numero_parte'):
        sugerencias = _buscar_sugerencias_patron_por_numero_parte(datos['numero_parte'])
        if sugerencias:
            messages.info(request, 'Selecciona una sugerencia de patrón para precargar datos.')
        else:
            messages.warning(
                request,
                'No se encontró número de parte activo; puedes capturar los datos manualmente.',
            )

    return ConceptoForm(initial=datos, instance=instance, documento=documento), sugerencias


def _buscar_serie_en_form(request, instance=None, documento=None):
    datos = _datos_concepto_desde_post(request)
    sugerencias = []
    if not datos.get('serie'):
        messages.warning(request, 'Captura una serie para buscar patrón.')
    else:
        sugerencias = _buscar_sugerencias_patron_por_serie(datos['serie'])
        if sugerencias:
            messages.info(request, 'Selecciona una sugerencia de patrón para precargar datos.')
        else:
            messages.warning(request, 'No se encontraron patrones activos para la serie.')

    return ConceptoForm(initial=datos, instance=instance, documento=documento), sugerencias


def _buscar_historial_en_form(request, instance=None, documento=None):
    datos = _datos_concepto_desde_post(request)
    debe_buscar_historial = bool(datos.get('numero_parte') or datos.get('serie'))
    sugerencias = _buscar_sugerencias_historial(datos) if debe_buscar_historial else []

    if sugerencias:
        messages.info(request, 'Selecciona una sugerencia de Historial para precargar datos.')
    elif debe_buscar_historial:
        messages.warning(
            request,
            'No se encontraron coincidencias en historial confirmado.',
        )
    else:
        messages.warning(request, 'Captura número de parte o serie para buscar historial.')

    return ConceptoForm(initial=datos, instance=instance, documento=documento), sugerencias


def _usar_sugerencia_en_form(request, instance=None, documento=None):
    datos = _datos_concepto_desde_post(request)
    if request.POST.get('sugerencia_origen') == 'patron':
        datos['numero_parte'] = request.POST.get('sugerencia_numero_parte', '').strip()
        datos['modelo'] = request.POST.get('sugerencia_modelo', '').strip()
        datos['descripcion'] = request.POST.get('sugerencia_descripcion', '').strip()
    else:
        sugerencia = get_object_or_404(
            HistorialCoincidencia,
            pk=request.POST.get('sugerencia_id'),
        )
        datos['numero_parte'] = sugerencia.numero_parte
        if not datos.get('serie'):
            datos['serie'] = sugerencia.serie
        datos['modelo'] = sugerencia.modelo
        datos['descripcion'] = sugerencia.descripcion
    messages.success(request, 'Sugerencia aplicada. Revisa los datos y guarda el concepto.')

    return ConceptoForm(initial=datos, instance=instance, documento=documento)


def _datos_concepto_desde_post(request):
    datos = {campo: request.POST.get(campo, '') for campo in ConceptoForm.Meta.fields}
    for campo in ('numero_parte', 'serie', 'descripcion'):
        datos[campo] = datos.get(campo, '').strip()
    return datos


def _aplicar_numero_parte_activo(request, datos, avisar_sin_numero=False):
    numero_parte = datos.get('numero_parte', '').strip().upper()
    datos['numero_parte'] = numero_parte
    if not numero_parte:
        if avisar_sin_numero:
            messages.warning(
                request,
                'Captura un numero de parte para buscar.',
            )
        return False

    try:
        parte = NumeroParte.objects.get(numero_parte__iexact=numero_parte)
    except NumeroParte.DoesNotExist:
        return False

    if not parte.activo:
        messages.warning(
            request,
            'El número de parte existe pero está inactivo.',
        )
        return False

    datos['modelo'] = parte.modelo
    datos['descripcion'] = parte.descripcion
    messages.success(request, 'Catalogo: numero de parte activo encontrado.')
    return True


def _buscar_sugerencias_historial(datos):
    numero_parte = datos.get('numero_parte', '').strip().upper()
    serie = datos.get('serie', '').strip().upper()
    if not numero_parte and not serie:
        return []

    queryset = HistorialCoincidencia.objects.filter(
        usar_para_biblioteca=True,
    ).filter(
        Q(documento__isnull=True)
        | Q(documento__status=DocumentoConceptos.STATUS_CONFIRMADO)
    ).exclude(
        numero_parte='',
        serie='',
        descripcion='',
    )
    if numero_parte:
        queryset = queryset.filter(numero_parte__iexact=numero_parte)
    if serie:
        queryset = queryset.filter(serie__iexact=serie)

    return [
        _sugerencia_desde_historial(historial)
        for historial in queryset.order_by('-created_at', '-id')[:10]
    ]


def _sugerencia_desde_historial(historial):
    return {
        'id': historial.pk,
        'origen': 'historial',
        'origen_label': 'Historial',
        'numero_parte': historial.numero_parte,
        'serie': historial.serie,
        'modelo': historial.modelo,
        'descripcion': historial.descripcion,
        'precio_unitario': '',
        'prefix': '',
        'sample_size': '',
        'confidence': '',
    }


def _patrones_activos():
    return PatronSerie.objects.filter(
        activo=True,
        campo_identificador=PatronSerie.CAMPO_SERIE,
    ).order_by('-updated_at', '-id')


def _buscar_sugerencias_patron_por_numero_parte(numero_parte):
    numero_parte = (numero_parte or '').strip().upper()
    if not numero_parte:
        return []
    patrones = PatronSerie.objects.filter(
        activo=True,
        campo_identificador=PatronSerie.CAMPO_SERIE,
        numero_parte__iexact=numero_parte,
    ).order_by('prefix', '-updated_at', '-id')
    return [_sugerencia_desde_patron(patron) for patron in patrones[:10]]


def _buscar_sugerencias_patron_por_serie(serie):
    serie = (serie or '').strip().upper()
    if not serie:
        return []
    patrones = _patrones_activos()
    matches = [patron for patron in patrones if serie.startswith(patron.prefix)]
    if not matches:
        return []

    matches = sorted(matches, key=lambda item: (-len(item.prefix), item.prefix, item.numero_parte))
    longitud_ganadora = len(matches[0].prefix)
    ganadores = [patron for patron in matches if len(patron.prefix) == longitud_ganadora]
    return [_sugerencia_desde_patron(patron) for patron in ganadores[:10]]


def _sugerencia_desde_patron(patron):
    return {
        'id': '',
        'origen': 'patron',
        'origen_label': 'Patron',
        'numero_parte': patron.numero_parte,
        'serie': '',
        'modelo': patron.modelo,
        'descripcion': patron.descripcion,
        'precio_unitario': '',
        'prefix': patron.prefix,
        'sample_size': patron.sample_size,
        'confidence': patron.confidence,
    }


@require_POST
@permission_required('conceptos.puede_confirmar_documentoconceptos')
def documento_confirmar(request, pk):
    documento = get_object_or_404(DocumentoConceptos, pk=pk)
    if documento.status == DocumentoConceptos.STATUS_BORRADOR:
        documento.status = DocumentoConceptos.STATUS_CONFIRMADO
        documento.save(update_fields=['status', 'updated_at'])
        for concepto in documento.conceptos.all():
            historial = registrar_historial_concepto(concepto, usuario=request.user)
            if historial:
                HistorialCoincidencia.objects.filter(pk=historial.pk).update(
                    documento=documento,
                    confirmado_por=request.user,
                    usar_para_biblioteca=True,
                )
        analizar_historial_para_propuestas()
    messages.success(request, 'Factura confirmada correctamente.')
    return redirect('conceptos:documento_detail', pk=documento.pk)


@require_POST
@permission_required('conceptos.puede_cancelar_documentoconceptos')
def documento_cancelar(request, pk):
    documento = get_object_or_404(DocumentoConceptos, pk=pk)
    if documento.status != DocumentoConceptos.STATUS_CANCELADO:
        documento.status = DocumentoConceptos.STATUS_CANCELADO
        documento.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Factura cancelada correctamente.')
    return redirect('conceptos:documento_detail', pk=documento.pk)
