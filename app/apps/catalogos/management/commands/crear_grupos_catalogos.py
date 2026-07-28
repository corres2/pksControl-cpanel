from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


GRUPOS_CATALOGOS = {
    'Catalogos - Consulta': [
        'catalogos.view_numeroparte',
        'catalogos.view_claveproductoserviciosat',
    ],
    'Catalogos - Importacion': [
        'catalogos.view_numeroparte',
        'catalogos.puede_importar_numeroparte',
        'catalogos.view_claveproductoserviciosat',
        'catalogos.puede_importar_claves_sat',
    ],
    'Catalogos - Auditoria': [
        'catalogos.puede_ver_historial_cargas_catalogo',
    ],
    'Catalogos - Administrador': [
        'catalogos.view_numeroparte',
        'catalogos.add_numeroparte',
        'catalogos.change_numeroparte',
        'catalogos.delete_numeroparte',
        'catalogos.puede_importar_numeroparte',
        'catalogos.view_claveproductoserviciosat',
        'catalogos.add_claveproductoserviciosat',
        'catalogos.change_claveproductoserviciosat',
        'catalogos.delete_claveproductoserviciosat',
        'catalogos.puede_importar_claves_sat',
        'catalogos.view_cargacatalogo',
        'catalogos.puede_ver_historial_cargas_catalogo',
    ],
}


class Command(BaseCommand):
    help = 'Crea o actualiza grupos base para permisos del modulo catalogos.'

    def handle(self, *args, **options):
        creados = 0
        actualizados = 0

        for nombre_grupo, permisos_requeridos in GRUPOS_CATALOGOS.items():
            grupo, creado = Group.objects.get_or_create(name=nombre_grupo)
            permisos = self._obtener_permisos(permisos_requeridos, nombre_grupo)
            grupo.permissions.set(permisos)

            if creado:
                creados += 1
                accion = 'creado'
            else:
                actualizados += 1
                accion = 'actualizado'

            self.stdout.write(
                self.style.SUCCESS(
                    f"Grupo {accion}: {nombre_grupo} ({len(permisos)} permisos)"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Resumen: {creados} grupos creados, {actualizados} grupos actualizados."
            )
        )

    def _obtener_permisos(self, permisos_requeridos, nombre_grupo):
        permisos = []

        for permiso_completo in permisos_requeridos:
            app_label, codename = permiso_completo.split('.', 1)
            permiso = Permission.objects.filter(
                content_type__app_label=app_label,
                codename=codename,
            ).first()

            if permiso is None:
                self.stderr.write(
                    self.style.WARNING(
                        f"Permiso faltante para {nombre_grupo}: {permiso_completo}"
                    )
                )
                continue

            permisos.append(permiso)

        return permisos
