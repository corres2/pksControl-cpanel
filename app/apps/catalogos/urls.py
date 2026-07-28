from django.urls import path

from apps.catalogos.views import (
    cargas_list,
    descargar_plantilla_numeros_parte,
    descargar_plantilla_sat,
    exportar_cargas_csv,
    exportar_numeros_parte_csv,
    exportar_sat_csv,
    importar_numeros_parte,
    importar_sat,
    numero_parte_activar,
    numero_parte_create,
    numero_parte_detail,
    numero_parte_inactivar,
    numero_parte_update,
    numeros_parte_list,
    sat_list,
)

app_name = 'catalogos'

urlpatterns = [
    path('cargas/', cargas_list, name='cargas_list'),
    path('cargas/exportar/', exportar_cargas_csv, name='exportar_cargas_csv'),
    path('numeros-parte/', numeros_parte_list, name='numeros_parte_list'),
    path(
        'numeros-parte/exportar/',
        exportar_numeros_parte_csv,
        name='exportar_numeros_parte_csv',
    ),
    path('numeros-parte/nuevo/', numero_parte_create, name='numero_parte_create'),
    path('numeros-parte/importar/', importar_numeros_parte, name='importar_numeros_parte'),
    path(
        'numeros-parte/plantilla/',
        descargar_plantilla_numeros_parte,
        name='plantilla_numeros_parte',
    ),
    path(
        'numeros-parte/<int:pk>/activar/',
        numero_parte_activar,
        name='numero_parte_activar',
    ),
    path(
        'numeros-parte/<int:pk>/inactivar/',
        numero_parte_inactivar,
        name='numero_parte_inactivar',
    ),
    path('numeros-parte/<int:pk>/', numero_parte_detail, name='numero_parte_detail'),
    path('numeros-parte/<int:pk>/editar/', numero_parte_update, name='numero_parte_update'),
    path('sat/', sat_list, name='sat_list'),
    path('sat/exportar/', exportar_sat_csv, name='exportar_sat_csv'),
    path('sat/importar/', importar_sat, name='importar_sat'),
    path('sat/plantilla/', descargar_plantilla_sat, name='plantilla_sat'),
]
