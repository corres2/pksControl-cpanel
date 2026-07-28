from django.contrib import admin

from apps.catalogos.models import CargaCatalogo, ClaveProductoServicioSAT, NumeroParte


@admin.register(CargaCatalogo)
class CargaCatalogoAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'tipo_catalogo',
        'archivo_nombre',
        'usuario',
        'total_procesadas',
        'total_creadas',
        'total_actualizadas',
        'total_errores',
        'estado',
    )
    list_filter = ('tipo_catalogo', 'estado', 'created_at')
    search_fields = ('archivo_nombre', 'usuario__username')


@admin.register(NumeroParte)
class NumeroParteAdmin(admin.ModelAdmin):
    list_display = ('numero_parte', 'modelo', 'descripcion', 'fraccion')
    search_fields = ('numero_parte', 'modelo', 'descripcion', 'fraccion')


@admin.register(ClaveProductoServicioSAT)
class ClaveProductoServicioSATAdmin(admin.ModelAdmin):
    list_display = ('clave', 'descripcion', 'fecha_inicio_vigencia', 'fecha_fin_vigencia')
    search_fields = ('clave', 'descripcion', 'palabras_similares')
