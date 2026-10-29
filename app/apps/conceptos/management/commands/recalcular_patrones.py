from django.core.management.base import BaseCommand

from apps.conceptos.models import PatronSerie
from apps.conceptos.services import analizar_historial_para_propuestas


class Command(BaseCommand):
    help = 'Recalcula la biblioteca de patrones de serie a partir del historial confirmado.'

    def handle(self, *args, **options):
        analizar_historial_para_propuestas()
        self.stdout.write('Biblioteca de patrones recalculada.')
        for estado, etiqueta in PatronSerie.ESTADOS:
            total = PatronSerie.objects.filter(estado=estado).count()
            self.stdout.write(f'- {etiqueta}: {total}')
        self.stdout.write(f'- Activos: {PatronSerie.objects.filter(activo=True).count()}')
