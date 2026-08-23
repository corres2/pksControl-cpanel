import csv
import csv
import re
import unicodedata
from datetime import datetime
from io import StringIO

from apps.catalogos.models import ClaveProductoServicioSAT, NumeroParte

MAX_FILAS_NUMEROS_PARTE = 5000
MAX_MUESTRA_PREVIEW = 10


def importar_numeros_parte_csv(archivo):
    preview = analizar_numeros_parte_csv(archivo)
    resultado = guardar_numeros_parte_desde_filas(preview['filas'])
    resultado['errores'] = preview['errores']
    return resultado


def analizar_numeros_parte_csv(archivo, limite=MAX_FILAS_NUMEROS_PARTE):
    preview = {
        'archivo_nombre': getattr(archivo, 'name', ''),
        'filas_validas': 0,
        'crearian': 0,
        'actualizarian': 0,
        'errores': [],
        'muestra': [],
        'filas': [],
    }
    numeros_en_archivo = set()
    limite_excedido = False

    for fila_numero, fila in _leer_archivo_numeros_parte(archivo):
        valores = _normalizar_fila(fila, 4)
        numero_parte, modelo, descripcion, fraccion = valores

        if fila_numero == 1 and _parece_encabezado_numero_parte(numero_parte):
            continue
        if not any(valores):
            continue

        if len(preview['filas']) + len(preview['errores']) >= limite:
            limite_excedido = True
            break

        if not numero_parte:
            _agregar_error(preview, fila_numero, 'numero_parte es requerido.')
            continue
        if not descripcion:
            _agregar_error(preview, fila_numero, 'descripcion es requerida.')
            continue
        if numero_parte in numeros_en_archivo:
            _agregar_error(preview, fila_numero, 'numero_parte duplicado dentro del archivo.')
            continue

        numeros_en_archivo.add(numero_parte)
        fila_normalizada = {
            'fila': fila_numero,
            'numero_parte': numero_parte,
            'modelo': modelo,
            'descripcion': descripcion,
            'fraccion': fraccion,
        }
        preview['filas'].append(fila_normalizada)
        if len(preview['muestra']) < MAX_MUESTRA_PREVIEW:
            preview['muestra'].append(fila_normalizada)

    if limite_excedido:
        _agregar_error(preview, limite + 1, f'El archivo excede el limite de {limite} filas.')

    existentes = set()
    if preview['filas']:
        existentes = set(
            NumeroParte.objects.filter(
                numero_parte__in=[fila['numero_parte'] for fila in preview['filas']]
            ).values_list('numero_parte', flat=True)
        )
    preview['filas_validas'] = len(preview['filas'])
    preview['actualizarian'] = sum(
        1 for fila in preview['filas'] if fila['numero_parte'] in existentes
    )
    preview['crearian'] = preview['filas_validas'] - preview['actualizarian']
    return preview


def guardar_numeros_parte_desde_filas(filas):
    resultado = _resultado_base()

    for fila in filas:
        _, creado = NumeroParte.objects.update_or_create(
            numero_parte=fila['numero_parte'],
            defaults={
                'modelo': fila['modelo'],
                'descripcion': fila['descripcion'],
                'fraccion': fila['fraccion'],
            },
        )
        resultado['procesadas'] += 1
        _contar_guardado(resultado, creado)

    return resultado


def importar_claves_sat_csv(archivo):
    resultado = _resultado_base()
    datos_iniciados = False

    for fila_numero, fila in _leer_csv(archivo):
        valores = _normalizar_fila(fila, 9)
        clave = valores[0]

        if not datos_iniciados:
            if not _parece_clave_sat(clave):
                continue
            datos_iniciados = True

        if not any(valores):
            continue

        resultado['procesadas'] += 1

        if not clave:
            _agregar_error(resultado, fila_numero, 'clave es requerida.')
            continue
        if not _parece_clave_sat(clave):
            _agregar_error(resultado, fila_numero, 'clave debe ser numerica de 8 digitos.')
            continue

        descripcion = valores[1]
        if not descripcion:
            _agregar_error(resultado, fila_numero, 'descripcion es requerida.')
            continue

        _, creado = ClaveProductoServicioSAT.objects.update_or_create(
            clave=clave,
            defaults={
                'descripcion': descripcion,
                'incluir_iva_trasladado': valores[2],
                'incluir_ieps_trasladado': valores[3],
                'complemento_que_debe_incluir': valores[4],
                'fecha_inicio_vigencia': _parsear_fecha(valores[5]),
                'fecha_fin_vigencia': _parsear_fecha(valores[6]),
                'estimulo_franja_fronteriza': valores[7],
                'palabras_similares': valores[8],
            },
        )
        _contar_guardado(resultado, creado)

    return resultado


def _resultado_base():
    return {
        'procesadas': 0,
        'creadas': 0,
        'actualizadas': 0,
        'errores': [],
    }


def _leer_csv(archivo):
    archivo.seek(0)
    contenido = archivo.read()
    if isinstance(contenido, bytes):
        texto = _decodificar(contenido)
    else:
        texto = contenido

    lector = csv.reader(StringIO(texto))
    for indice, fila in enumerate(lector, start=1):
        yield indice, fila


def _leer_archivo_numeros_parte(archivo):
    extension = getattr(archivo, 'name', '').lower()
    if extension.endswith('.csv'):
        yield from _leer_csv(archivo)
        return
    if extension.endswith('.xlsx'):
        yield from _leer_xlsx(archivo)
        return
    raise ValueError('Formato no soportado. Usa CSV o XLSX.')


def _leer_xlsx(archivo):
    from openpyxl import load_workbook

    archivo.seek(0)
    workbook = load_workbook(archivo, read_only=True, data_only=True)
    try:
        for indice, fila in enumerate(
            workbook.active.iter_rows(values_only=True), start=1
        ):
            yield indice, [valor if valor is not None else '' for valor in fila[:4]]
    finally:
        workbook.close()


def _decodificar(contenido):
    for codificacion in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return contenido.decode('utf-8', errors='replace')


def _normalizar_fila(fila, longitud):
    valores = [str(valor).strip() for valor in fila[:longitud]]
    return valores + [''] * (longitud - len(valores))


def _parece_encabezado_numero_parte(valor):
    normalizado = _sin_acentos(valor).lower()
    return 'numero' in normalizado or 'parte' in normalizado


def _sin_acentos(valor):
    return ''.join(
        caracter
        for caracter in unicodedata.normalize('NFKD', valor)
        if not unicodedata.combining(caracter)
    )


def _parece_clave_sat(valor):
    return bool(re.fullmatch(r'\d{8}', valor or ''))


def _parsear_fecha(valor):
    if not valor:
        return None

    for formato in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(valor, formato).date()
        except ValueError:
            continue
    return None


def _agregar_error(resultado, fila, error):
    resultado['errores'].append({'fila': fila, 'error': error})


def _contar_guardado(resultado, creado):
    if creado:
        resultado['creadas'] += 1
    else:
        resultado['actualizadas'] += 1
