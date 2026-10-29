import csv
from io import BytesIO

from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone

from apps.catalogos.models import CargaCatalogo, ClaveProductoServicioSAT, NumeroParte
from apps.conceptos.models import Concepto, DocumentoConceptos, HistorialCoincidencia, PatronSerie

XLSX_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

TABLAS_EXPORTABLES = {
    'patrones': ('Biblioteca de patrones de serie', PatronSerie),
    'historial': ('Historial de coincidencias', HistorialCoincidencia),
    'documentos': ('Facturas', DocumentoConceptos),
    'conceptos': ('Conceptos de facturas', Concepto),
    'numeros_parte': ('Números de parte', NumeroParte),
    'carta_porte': ('Catálogo Carta Porte', ClaveProductoServicioSAT),
    'cargas': ('Bitácora de cargas de catálogos', CargaCatalogo),
}


class _Eco:
    def write(self, valor):
        return valor


def _columnas(modelo):
    return [campo.attname for campo in modelo._meta.concrete_fields]


def _filas(modelo, columnas):
    for fila in modelo.objects.order_by('pk').values_list(*columnas).iterator(chunk_size=2000):
        yield [_valor_celda(valor) for valor in fila]


def _valor_celda(valor):
    if hasattr(valor, 'tzinfo') and valor.tzinfo is not None:
        return timezone.localtime(valor).replace(tzinfo=None)
    if isinstance(valor, (dict, list)):
        return str(valor)
    return valor


def _nombre_archivo(clave, extension):
    return f'{clave}_{timezone.localtime().strftime("%Y%m%d_%H%M")}.{extension}'


def exportar_tabla_csv(clave):
    _titulo, modelo = TABLAS_EXPORTABLES[clave]
    columnas = _columnas(modelo)
    escritor = csv.writer(_Eco())

    def contenido():
        yield '\ufeff'
        yield escritor.writerow(columnas)
        for fila in _filas(modelo, columnas):
            yield escritor.writerow(fila)

    respuesta = StreamingHttpResponse(contenido(), content_type='text/csv; charset=utf-8')
    respuesta['Content-Disposition'] = f'attachment; filename="{_nombre_archivo(clave, "csv")}"'
    return respuesta


def exportar_tabla_xlsx(clave):
    from openpyxl import Workbook

    titulo, modelo = TABLAS_EXPORTABLES[clave]
    columnas = _columnas(modelo)
    libro = Workbook(write_only=True)
    hoja = libro.create_sheet(title=titulo[:31])
    hoja.append(columnas)
    for fila in _filas(modelo, columnas):
        hoja.append(fila)
    salida = BytesIO()
    libro.save(salida)
    respuesta = HttpResponse(salida.getvalue(), content_type=XLSX_CONTENT_TYPE)
    respuesta['Content-Disposition'] = f'attachment; filename="{_nombre_archivo(clave, "xlsx")}"'
    return respuesta


def resumen_tablas():
    return [
        {'clave': clave, 'titulo': titulo, 'total': modelo.objects.count()}
        for clave, (titulo, modelo) in TABLAS_EXPORTABLES.items()
    ]
