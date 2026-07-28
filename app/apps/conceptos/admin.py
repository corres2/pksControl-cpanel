from django.contrib import admin

from apps.conceptos.models import (
    Concepto,
    DocumentoConceptos,
    HistorialCoincidencia,
    PatronSerie,
)


class ConceptoInline(admin.TabularInline):
    model = Concepto
    extra = 0


@admin.register(DocumentoConceptos)
class DocumentoConceptosAdmin(admin.ModelAdmin):
    inlines = [ConceptoInline]
    list_display = ('folio', 'fuente', 'status', 'total', 'usuario', 'created_at')
    list_filter = ('fuente', 'status', 'created_at')
    search_fields = ('folio', 'observaciones', 'usuario__username')


@admin.register(Concepto)
class ConceptoAdmin(admin.ModelAdmin):
    list_display = (
        'documento',
        'numero_parte',
        'serie',
        'descripcion',
        'cantidad',
        'precio_unitario',
        'total_concepto',
    )
    search_fields = ('numero_parte', 'serie', 'modelo', 'descripcion', 'documento__folio')


@admin.register(PatronSerie)
class PatronSerieAdmin(admin.ModelAdmin):
    list_display = (
        'prefix',
        'numero_parte',
        'modelo',
        'estado',
        'sample_size',
        'evidencias_totales',
        'series_unicas',
        'confidence',
        'activo',
        'source',
    )
    list_filter = ('estado', 'activo', 'source', 'campo_identificador')
    search_fields = ('prefix', 'numero_parte', 'modelo', 'descripcion', 'motivo_conflicto')


@admin.register(HistorialCoincidencia)
class HistorialCoincidenciaAdmin(admin.ModelAdmin):
    list_display = (
        'serie',
        'numero_parte',
        'modelo',
        'regla_usada',
        'match_type',
        'usar_para_biblioteca',
        'created_at',
    )
    list_filter = (
        'regla_usada',
        'match_type',
        'usar_para_biblioteca',
        'confirmado_en_importacion',
    )
    search_fields = ('serie', 'numero_parte', 'modelo', 'descripcion')
