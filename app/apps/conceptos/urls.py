from django.urls import path

from apps.conceptos.views import (
    concepto_create,
    concepto_bajar,
    concepto_delete,
    concepto_subir,
    concepto_update,
    conceptos_reordenar,
    conceptos_importar,
    conceptos_importar_cancelar,
    conceptos_importar_confirmar,
    conceptos_autocomplete,
    documento_cancelar,
    documento_confirmar,
    documento_create,
    documento_detail,
    documento_exportar_word,
    documento_update,
    documentos_list,
)

app_name = 'conceptos'

urlpatterns = [
    path('', documentos_list, name='documentos_list'),
    path('autocomplete/', conceptos_autocomplete, name='conceptos_autocomplete'),
    path('nuevo/', documento_create, name='documento_create'),
    path('<int:pk>/', documento_detail, name='documento_detail'),
    path('<int:pk>/exportar-word/', documento_exportar_word, name='documento_exportar_word'),
    path('<int:pk>/editar/', documento_update, name='documento_update'),
    path('<int:pk>/importar/', conceptos_importar, name='conceptos_importar'),
    path(
        '<int:pk>/importar/confirmar/',
        conceptos_importar_confirmar,
        name='conceptos_importar_confirmar',
    ),
    path(
        '<int:pk>/importar/cancelar/',
        conceptos_importar_cancelar,
        name='conceptos_importar_cancelar',
    ),
    path('<int:pk>/conceptos/nuevo/', concepto_create, name='concepto_create'),
    path(
        '<int:pk>/conceptos/<int:concepto_id>/editar/',
        concepto_update,
        name='concepto_update',
    ),
    path(
        '<int:pk>/conceptos/<int:concepto_id>/subir/',
        concepto_subir,
        name='concepto_subir',
    ),
    path(
        '<int:pk>/conceptos/<int:concepto_id>/bajar/',
        concepto_bajar,
        name='concepto_bajar',
    ),
    path('<int:pk>/conceptos/reordenar/', conceptos_reordenar, name='conceptos_reordenar'),
    path(
        '<int:pk>/conceptos/<int:concepto_id>/quitar/',
        concepto_delete,
        name='concepto_delete',
    ),
    path('<int:pk>/confirmar/', documento_confirmar, name='documento_confirmar'),
    path('<int:pk>/cancelar/', documento_cancelar, name='documento_cancelar'),
]
