from collections import Counter, defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.conceptos.models import PatronSerie, normalizar_texto


LIMITE_EJEMPLOS = 5


class Command(BaseCommand):
    help = 'Audita patrones de serie sin modificar datos.'

    def handle(self, *args, **options):
        patrones = list(PatronSerie.objects.all())

        self.stdout.write('Auditoria de patrones de serie')
        self.stdout.write('============================')
        self.stdout.write(f'Total PatronSerie: {len(patrones)}')
        self.stdout.write('')

        self._imprimir_conteos('PatronSerie por source', _conteos_patron_source())
        self._imprimir_conteos('PatronSerie por estado', _conteos_patron_estado())

        activos = sum(1 for patron in patrones if patron.activo)
        prefijos_duplicados = _duplicados(patrones, lambda item: _normalizar_prefix(item.prefix))
        prefix_varios_numero_parte = _conflictos_por_prefix(patrones)
        combinaciones_repetidas = _duplicados(
            patrones,
            lambda item: (_normalizar_prefix(item.prefix), normalizar_texto(item.numero_parte)),
        )
        conflictos = _conflictos_patrones(patrones)

        self.stdout.write('Activos/inactivos PatronSerie:')
        self.stdout.write(f'- Activos: {activos}')
        self.stdout.write(f'- Inactivos: {len(patrones) - activos}')
        self.stdout.write('')

        self._imprimir_bloque('Prefijos duplicados exactos', prefijos_duplicados)
        self._imprimir_bloque('Mismo prefix asociado a varios numero_parte', prefix_varios_numero_parte)
        self._imprimir_bloque('Misma combinacion prefix + numero_parte repetida', combinaciones_repetidas)
        self._imprimir_bloque('Conflictos', conflictos)

        self.stdout.write('Calidad de datos:')
        self.stdout.write(f'- PatronSerie con firma_texto vacia: {_patrones_firma_texto_vacia(patrones)}')
        self.stdout.write(f'- PatronSerie con firma_json vacia: {_firma_json_vacia(patrones)}')
        self.stdout.write(f'- PatronSerie con sample_size < 3: {_sample_size_menor_3(patrones)}')
        self.stdout.write(f'- PatronSerie con confidence fuera de rango: {_confidence_fuera_rango(patrones)}')
        self.stdout.write('')

        self.stdout.write(f'Duplicados logicos restantes: {len(prefijos_duplicados) + len(combinaciones_repetidas)}')
        self.stdout.write(
            f'Patrones con series_unicas >= 3: {sum(1 for patron in patrones if patron.series_unicas >= 3)}'
        )
        self.stdout.write(
            f'Aprobados activos: {sum(1 for patron in patrones if patron.estado == "aprobado" and patron.activo)}'
        )
        self.stdout.write(
            f'Observados: {sum(1 for patron in patrones if patron.estado == "observado")}'
        )
        self.stdout.write(
            f'En crecimiento: {sum(1 for patron in patrones if patron.estado == "en_crecimiento")}'
        )
        self.stdout.write(
            f'Aprobados automaticos: {sum(1 for patron in patrones if patron.source == "evidence_autoapproved")}'
        )
        self.stdout.write(
            f'Conflictos: {sum(1 for patron in patrones if patron.estado == "conflicto")}'
        )
        self.stdout.write(
            f'Evidencias totales acumuladas: {sum(patron.evidencias_totales for patron in patrones)}'
        )
        self.stdout.write(
            f'Series unicas acumuladas: {sum(patron.series_unicas for patron in patrones)}'
        )
        self.stdout.write(self.style.SUCCESS('Auditoria finalizada. No se modificaron datos.'))

    def _imprimir_conteos(self, titulo, conteos):
        self.stdout.write(f'{titulo}:')
        if not conteos:
            self.stdout.write('- Sin registros')
        for clave, total in conteos:
            self.stdout.write(f'- {clave or "(vacio)"}: {total}')
        self.stdout.write('')

    def _imprimir_bloque(self, titulo, items):
        self.stdout.write(f'{titulo}: {len(items)}')
        for item in items[:LIMITE_EJEMPLOS]:
            self.stdout.write(f'- {item}')
        if len(items) > LIMITE_EJEMPLOS:
            self.stdout.write(f'- ... {len(items) - LIMITE_EJEMPLOS} mas')
        self.stdout.write('')


def _conteos_patron_source():
    return PatronSerie.objects.values_list('source').annotate(total=Count('id')).order_by('source')


def _conteos_patron_estado():
    return PatronSerie.objects.values_list('estado').annotate(total=Count('id')).order_by('estado')


def _normalizar_prefix(prefix):
    return (prefix or '').strip().upper()


def _duplicados(patrones, key_func):
    contador = Counter(key_func(patron) for patron in patrones if key_func(patron))
    return [
        _formatear_key_total(clave, total)
        for clave, total in contador.items()
        if total > 1
    ]


def _conflictos_por_prefix(patrones):
    por_prefix = defaultdict(set)
    for patron in patrones:
        prefix = _normalizar_prefix(patron.prefix)
        numero_parte = normalizar_texto(patron.numero_parte)
        if prefix and numero_parte:
            por_prefix[prefix].add(numero_parte)
    return [
        f'{prefix}: {len(numero_partes)} numero_parte ({", ".join(sorted(numero_partes)[:3])})'
        for prefix, numero_partes in por_prefix.items()
        if len(numero_partes) > 1
    ]


def _conflictos_patrones(patrones):
    return [
        f'{patron.prefix} -> {patron.numero_parte}: {patron.motivo_conflicto or "conflicto"}'
        for patron in patrones
        if getattr(patron, 'estado', '') == 'conflicto' or patron.motivo_conflicto
    ]


def _formatear_key_total(clave, total):
    if isinstance(clave, tuple):
        clave = ' | '.join(str(parte) for parte in clave)
    return f'{clave}: {total}'


def _patrones_firma_texto_vacia(patrones):
    return sum(1 for patron in patrones if not (patron.firma_texto or '').strip())


def _firma_json_vacia(registros):
    return sum(1 for registro in registros if not getattr(registro, 'firma_json', None))


def _sample_size_menor_3(registros):
    return sum(1 for registro in registros if registro.sample_size < 3)


def _confidence_fuera_rango(registros):
    minimo = Decimal('0')
    maximo = Decimal('1')
    return sum(1 for registro in registros if registro.confidence < minimo or registro.confidence > maximo)
