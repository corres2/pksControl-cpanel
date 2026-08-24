import csv
from datetime import datetime, time
from io import BytesIO
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.catalogos.forms import CSVUploadForm, NumeroParteForm
from apps.catalogos.models import CargaCatalogo, ClaveProductoServicioSAT, NumeroParte
from apps.catalogos.services.importacion import (
    analizar_numeros_parte_csv,
    guardar_numeros_parte_desde_filas,
    importar_claves_sat_csv,
)

PREVIEW_NUMEROS_PARTE_SESSION_KEY = 'catalogos_preview_numeros_parte'


def _datetime_en_dia(fecha, hora):
    valor = datetime.combine(fecha, hora)
    if timezone.is_naive(valor):
        return timezone.make_aware(valor, timezone.get_current_timezone())
    return valor


def _numeros_parte_filtrados(request):
    q = request.GET.get('q', '').strip()
    modelo = request.GET.get('modelo', '').strip()
    fraccion = request.GET.get('fraccion', '').strip()
    estado = request.GET.get('estado', 'activos').strip() or 'activos'
    queryset = NumeroParte.objects.all().order_by('numero_parte')

    if estado not in {'activos', 'inactivos', 'todos'}:
        estado = 'activos'
    if estado == 'activos':
        queryset = queryset.filter(activo=True)
    elif estado == 'inactivos':
        queryset = queryset.filter(activo=False)
    if q:
        queryset = queryset.filter(
            Q(numero_parte__icontains=q)
            | Q(modelo__icontains=q)
            | Q(descripcion__icontains=q)
            | Q(fraccion__icontains=q)
        )
    if modelo:
        queryset = queryset.filter(modelo__icontains=modelo)
    if fraccion:
        queryset = queryset.filter(fraccion__icontains=fraccion)

    return queryset, q, modelo, fraccion, estado


def _formatear_fecha_csv(valor):
    if not valor:
        return ''
    if timezone.is_aware(valor):
        valor = timezone.localtime(valor)
    return valor.strftime('%Y-%m-%d %H:%M:%S')


def _formatear_fecha_simple_csv(valor):
    if not valor:
        return ''
    return valor.strftime('%Y-%m-%d')


def _claves_sat_filtradas(request):
    q = request.GET.get('q', '').strip()
    iva = request.GET.get('iva', '').strip()
    ieps = request.GET.get('ieps', '').strip()
    vigente = request.GET.get('vigente', '').strip()
    queryset = ClaveProductoServicioSAT.objects.all().order_by('clave')

    if q:
        queryset = queryset.filter(
            Q(clave__icontains=q)
            | Q(descripcion__icontains=q)
            | Q(palabras_similares__icontains=q)
        )
    if iva:
        queryset = queryset.filter(incluir_iva_trasladado__icontains=iva)
    if ieps:
        queryset = queryset.filter(incluir_ieps_trasladado__icontains=ieps)
    if vigente == '1':
        hoy = timezone.localdate()
        queryset = queryset.filter(
            Q(fecha_fin_vigencia__isnull=True) | Q(fecha_fin_vigencia__gte=hoy)
        )

    return queryset, q, iva, ieps, vigente


def _cargas_filtradas(request):
    q = request.GET.get('q', '').strip()
    archivo = request.GET.get('archivo', '').strip()
    tipo_catalogo = request.GET.get('tipo_catalogo', '').strip()
    estado = request.GET.get('estado', '').strip()
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    fecha_error = ''
    queryset = CargaCatalogo.objects.select_related('usuario').order_by('-created_at')

    if q:
        queryset = queryset.filter(
            Q(tipo_catalogo__icontains=q)
            | Q(archivo_nombre__icontains=q)
            | Q(estado__icontains=q)
        )
    if archivo:
        queryset = queryset.filter(archivo_nombre__icontains=archivo)
    if tipo_catalogo:
        queryset = queryset.filter(tipo_catalogo__icontains=tipo_catalogo)
    if estado:
        queryset = queryset.filter(estado__icontains=estado)
    if fecha_desde:
        fecha = parse_date(fecha_desde)
        if fecha:
            queryset = queryset.filter(created_at__gte=_datetime_en_dia(fecha, time.min))
        else:
            fecha_error = 'Formato de fecha invalido. Usa YYYY-MM-DD.'
    if fecha_hasta:
        fecha = parse_date(fecha_hasta)
        if fecha:
            queryset = queryset.filter(created_at__lte=_datetime_en_dia(fecha, time.max))
        else:
            fecha_error = 'Formato de fecha invalido. Usa YYYY-MM-DD.'

    return queryset, q, fecha_desde, fecha_hasta, fecha_error


@permission_required('catalogos.puede_importar_numeroparte')
def descargar_plantilla_numeros_parte(request):
    return _crear_csv_descarga(
        'plantilla_numeros_parte.csv',
        [
            ['numero_parte', 'modelo', 'descripcion', 'fraccion'],
            ['NP-001', 'MOD-A', 'Sensor de temperatura', '9026.10.01'],
            ['NP-002', 'MOD-B', 'Cable de conexión', '8544.42.99'],
        ],
    )


@permission_required('catalogos.puede_importar_numeroparte')
def descargar_plantilla_numeros_parte_xlsx(request):
    return _crear_xlsx_descarga(
        'plantilla_numeros_parte.xlsx',
        [
            ['numero_parte', 'modelo', 'descripcion', 'fraccion'],
            ['NP-001', 'MOD-A', 'Sensor de temperatura', '9026.10.01'],
            ['NP-002', 'MOD-B', 'Cable de conexión', '8544.42.99'],
        ],
    )


@permission_required('catalogos.puede_importar_claves_sat')
def descargar_plantilla_sat(request):
    return _crear_csv_descarga(
        'plantilla_catalogo_carta_porte.csv',
        [
            ['c_ClaveProdServ', 'Descripción', 'Palabras similares', 'Material Peligroso', 'FechaInicioVigencia', 'FechaFinVigencia'],
            ['01010101', 'Ejemplo', '', '0', '', ''],
        ],
    )


@permission_required('catalogos.puede_importar_claves_sat')
def descargar_plantilla_sat_xlsx(request):
    return _crear_xlsx_descarga(
        'plantilla_catalogo_carta_porte.xlsx',
        [
            ['c_ClaveProdServ', 'Descripción', 'Palabras similares', 'Material Peligroso', 'FechaInicioVigencia', 'FechaFinVigencia'],
            ['01010101', 'Ejemplo', '', '0', '', ''],
        ],
    )


@permission_required('catalogos.puede_ver_historial_cargas_catalogo')
def cargas_list(request):
    queryset, q, fecha_desde, fecha_hasta, fecha_error = _cargas_filtradas(request)

    page_obj = Paginator(queryset, 25).get_page(request.GET.get('page'))
    filtros = request.GET.copy()
    filtros.pop('page', None)
    return render(
        request,
        'catalogos/cargas_list.html',
        {
            'page_obj': page_obj,
            'q': q,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'fecha_error': fecha_error,
            'querystring': filtros.urlencode(),
        },
    )


@permission_required('catalogos.puede_ver_historial_cargas_catalogo')
def exportar_cargas_csv(request):
    queryset, _q, _fecha_desde, _fecha_hasta, _fecha_error = _cargas_filtradas(request)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        'attachment; filename="historial_cargas_catalogos_filtrado.csv"'
    )
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(
        [
            'created_at',
            'tipo_catalogo',
            'archivo_nombre',
            'usuario',
            'total_procesadas',
            'total_creadas',
            'total_actualizadas',
            'total_errores',
            'estado',
            'errores_resumen',
        ]
    )
    for carga in queryset:
        writer.writerow(
            [
                _formatear_fecha_csv(carga.created_at),
                carga.tipo_catalogo,
                carga.archivo_nombre,
                carga.usuario or '',
                carga.total_procesadas,
                carga.total_creadas,
                carga.total_actualizadas,
                carga.total_errores,
                carga.estado,
                carga.errores_resumen,
            ]
        )

    return response


@permission_required('catalogos.view_numeroparte')
def numeros_parte_list(request):
    todos_los_numeros = NumeroParte.objects.all()
    try:
        total_numero_partes = todos_los_numeros.count()
    except (AttributeError, TypeError):
        total_numero_partes = len(todos_los_numeros)

    queryset, q, modelo, fraccion, estado = _numeros_parte_filtrados(request)

    page_obj = Paginator(queryset, 25).get_page(request.GET.get('page'))
    filtros = request.GET.copy()
    filtros.pop('page', None)
    return render(
        request,
        (
            'catalogos/partials/numeros_parte_resultados.html'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            else 'catalogos/numeros_parte_list.html'
        ),
        {
            'page_obj': page_obj,
            'q': q,
            'modelo': modelo,
            'fraccion': fraccion,
            'estado': estado,
            'querystring': filtros.urlencode(),
            'total_numero_partes': total_numero_partes,
        },
    )


@permission_required('catalogos.view_numeroparte')
def exportar_numeros_parte_csv(request):
    queryset, _q, _modelo, _fraccion, _estado = _numeros_parte_filtrados(request)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="numeros_parte_filtrado.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['numero_parte', 'modelo', 'descripcion', 'fraccion', 'updated_at'])
    for item in queryset:
        writer.writerow(
            [
                item.numero_parte,
                item.modelo,
                item.descripcion,
                item.fraccion,
                _formatear_fecha_csv(item.updated_at),
            ]
        )

    return response


@require_POST
@permission_required('catalogos.change_numeroparte')
def numero_parte_inactivar(request, pk):
    numero_parte = get_object_or_404(NumeroParte, pk=pk)
    numero_parte.activo = False
    numero_parte.save(update_fields=['activo', 'updated_at'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'activo': False, 'estado': 'Inactivo'})
    messages.success(request, 'Número de parte inactivado correctamente.')
    return redirect('catalogos:numero_parte_detail', pk=numero_parte.pk)


@require_POST
@permission_required('catalogos.change_numeroparte')
def numero_parte_activar(request, pk):
    numero_parte = get_object_or_404(NumeroParte, pk=pk)
    numero_parte.activo = True
    numero_parte.save(update_fields=['activo', 'updated_at'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'activo': True, 'estado': 'Activo'})
    messages.success(request, 'Número de parte activado correctamente.')
    return redirect('catalogos:numero_parte_detail', pk=numero_parte.pk)


@permission_required('catalogos.view_numeroparte')
def numero_parte_detail(request, pk):
    numero_parte = get_object_or_404(NumeroParte, pk=pk)
    return render(
        request,
        'catalogos/numeroparte_detail.html',
        {'numero_parte': numero_parte},
    )


@permission_required('catalogos.add_numeroparte')
def numero_parte_create(request):
    form = NumeroParteForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        numero_parte = form.save()
        messages.success(request, 'Número de parte creado correctamente.')
        return redirect('catalogos:numero_parte_detail', pk=numero_parte.pk)

    return render(
        request,
        'catalogos/numeroparte_form.html',
        {'form': form, 'titulo': 'Nuevo número de parte'},
    )


@permission_required('catalogos.change_numeroparte')
def numero_parte_update(request, pk):
    numero_parte = get_object_or_404(NumeroParte, pk=pk)
    form = NumeroParteForm(request.POST or None, instance=numero_parte)

    if request.method == 'POST' and form.is_valid():
        numero_parte = form.save()
        messages.success(request, 'Número de parte actualizado correctamente.')
        return redirect('catalogos:numero_parte_detail', pk=numero_parte.pk)

    return render(
        request,
        'catalogos/numeroparte_form.html',
        {
            'form': form,
            'titulo': 'Editar número de parte',
            'numero_parte': numero_parte,
        },
    )


@permission_required('catalogos.view_claveproductoserviciosat')
def sat_list(request):
    queryset, q, iva, ieps, vigente = _claves_sat_filtradas(request)

    page_obj = Paginator(queryset, 25).get_page(request.GET.get('page'))
    filtros = request.GET.copy()
    filtros.pop('page', None)
    return render(
        request,
        'catalogos/sat_list.html',
        {
            'page_obj': page_obj,
            'q': q,
            'iva': iva,
            'ieps': ieps,
            'vigente': vigente,
            'querystring': filtros.urlencode(),
        },
    )


@permission_required('catalogos.view_claveproductoserviciosat')
def exportar_sat_csv(request):
    queryset, _q, _iva, _ieps, _vigente = _claves_sat_filtradas(request)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="catalogo_carta_porte_filtrado.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(
        ['c_ClaveProdServ', 'Descripción', 'Palabras similares', 'Material Peligroso', 'FechaInicioVigencia', 'FechaFinVigencia']
    )
    for item in queryset:
        writer.writerow(
            [
                item.clave,
                item.descripcion,
                item.palabras_similares,
                item.complemento_que_debe_incluir,
                _formatear_fecha_simple_csv(item.fecha_inicio_vigencia),
                _formatear_fecha_simple_csv(item.fecha_fin_vigencia),
            ]
        )

    return response


@permission_required('catalogos.view_claveproductoserviciosat')
def exportar_sat_xlsx(request):
    queryset, _q, _iva, _ieps, _vigente = _claves_sat_filtradas(request)
    filas = [
        ['c_ClaveProdServ', 'Descripción', 'Palabras similares', 'Material Peligroso', 'FechaInicioVigencia', 'FechaFinVigencia']
    ]
    filas.extend(
        [
            item.clave,
            item.descripcion,
            item.palabras_similares,
            item.complemento_que_debe_incluir,
            _formatear_fecha_simple_csv(item.fecha_inicio_vigencia),
            _formatear_fecha_simple_csv(item.fecha_fin_vigencia),
        ]
        for item in queryset
    )
    return _crear_xlsx_descarga('catalogo_carta_porte_filtrado.xlsx', filas)


@permission_required('catalogos.puede_importar_numeroparte')
def importar_numeros_parte(request):
    resultado = None
    session = _obtener_session(request)
    preview = session.get(PREVIEW_NUMEROS_PARTE_SESSION_KEY)
    form = CSVUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and request.POST.get('accion') == 'cancelar':
        session.pop(PREVIEW_NUMEROS_PARTE_SESSION_KEY, None)
        messages.success(request, 'Importación cancelada.')
        return redirect('catalogos:importar_numeros_parte')

    if request.method == 'POST' and request.POST.get('accion') == 'confirmar':
        preview = session.get(PREVIEW_NUMEROS_PARTE_SESSION_KEY)
        if not preview:
            messages.error(request, 'No hay una importación pendiente por confirmar.')
            return redirect('catalogos:importar_numeros_parte')

        archivo = SimpleNamespace(name=preview.get('archivo_nombre', ''))
        try:
            resultado = guardar_numeros_parte_desde_filas(preview.get('filas', []))
            resultado['errores'] = preview.get('errores', [])
            _registrar_carga_catalogo(
                CargaCatalogo.TIPO_NUMEROS_PARTE,
                archivo,
                request.user,
                resultado,
            )
            _agregar_mensaje_resultado(request, resultado)
            session.pop(PREVIEW_NUMEROS_PARTE_SESSION_KEY, None)
            preview = None
        except Exception:
            _registrar_carga_fallida(
                CargaCatalogo.TIPO_NUMEROS_PARTE,
                archivo,
                request.user,
            )
            messages.error(request, 'La importación falló. Revisa el archivo e intenta de nuevo.')

    elif request.method == 'POST' and form.is_valid():
        archivo = form.cleaned_data['archivo']
        try:
            preview = analizar_numeros_parte_csv(archivo)
            session[PREVIEW_NUMEROS_PARTE_SESSION_KEY] = preview
            if hasattr(session, 'modified'):
                session.modified = True
        except Exception:
            messages.error(request, 'No se pudo analizar el archivo. Revisa el CSV o XLSX e intenta de nuevo.')

    return render(
        request,
        'catalogos/importar_numeros_parte.html',
        {'form': form, 'resultado': resultado, 'preview': preview},
    )


@permission_required('catalogos.puede_importar_claves_sat')
def importar_sat(request):
    resultado = None
    form = CSVUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        archivo = form.cleaned_data['archivo']
        try:
            resultado = importar_claves_sat_csv(archivo)
            _registrar_carga_catalogo(
                CargaCatalogo.TIPO_SAT_CLAVE_PRODUCTO_SERVICIO,
                archivo,
                request.user,
                resultado,
            )
            _agregar_mensaje_resultado(request, resultado)
        except ValueError as exc:
            _registrar_carga_fallida(
                CargaCatalogo.TIPO_SAT_CLAVE_PRODUCTO_SERVICIO,
                archivo,
                request.user,
            )
            messages.error(request, str(exc))
        except Exception:
            _registrar_carga_fallida(
                CargaCatalogo.TIPO_SAT_CLAVE_PRODUCTO_SERVICIO,
                archivo,
                request.user,
            )
            messages.error(request, 'La importación falló. Revisa el archivo e intenta de nuevo.')

    return render(
        request,
        'catalogos/importar_sat.html',
        {'form': form, 'resultado': resultado},
    )


def _agregar_mensaje_resultado(request, resultado):
    messages.success(
        request,
        (
            f"Importación terminada. Procesadas: {resultado['procesadas']}, "
            f"creadas: {resultado['creadas']}, actualizadas: {resultado['actualizadas']}, "
            f"errores: {len(resultado['errores'])}."
        ),
    )


def _obtener_session(request):
    if not hasattr(request, 'session'):
        request.session = {}
    return request.session


def _registrar_carga_catalogo(tipo_catalogo, archivo, usuario, resultado):
    errores = resultado.get('errores', [])
    estado = CargaCatalogo.ESTADO_EXITOSA
    if errores:
        estado = CargaCatalogo.ESTADO_CON_ERRORES

    CargaCatalogo.objects.create(
        tipo_catalogo=tipo_catalogo,
        archivo_nombre=getattr(archivo, 'name', ''),
        usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
        total_procesadas=resultado.get('procesadas', 0),
        total_creadas=resultado.get('creadas', 0),
        total_actualizadas=resultado.get('actualizadas', 0),
        total_errores=len(errores),
        estado=estado,
        errores_resumen=_resumir_errores(errores),
    )


def _registrar_carga_fallida(tipo_catalogo, archivo, usuario):
    CargaCatalogo.objects.create(
        tipo_catalogo=tipo_catalogo,
        archivo_nombre=getattr(archivo, 'name', ''),
        usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
        total_procesadas=0,
        total_creadas=0,
        total_actualizadas=0,
        total_errores=1,
        estado=CargaCatalogo.ESTADO_FALLIDA,
        errores_resumen='Error general durante importación.',
    )


def _resumir_errores(errores, limite=20):
    lineas = [
        f"Fila {error.get('fila')}: {error.get('error')}"
        for error in errores[:limite]
    ]
    if len(errores) > limite:
        lineas.append(f"... {len(errores) - limite} errores adicionales.")
    return '\n'.join(lineas)[:4000]


def _crear_csv_descarga(nombre_archivo, filas):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerows(filas)
    return response


def _crear_xlsx_descarga(nombre_archivo, filas):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    for fila in filas:
        sheet.append(fila)
    contenido = BytesIO()
    workbook.save(contenido)
    workbook.close()
    response = HttpResponse(
        contenido.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response
