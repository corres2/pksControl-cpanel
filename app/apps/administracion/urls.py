from django.urls import path

from apps.administracion import views

app_name = 'administracion'

urlpatterns = [
    path('usuarios/', views.usuarios_list, name='usuarios_list'),
    path('usuarios/nuevo/', views.usuario_create, name='usuario_create'),
    path('usuarios/<int:pk>/editar/', views.usuario_update, name='usuario_update'),
    path('exportaciones/', views.exportaciones, name='exportaciones'),
    path('exportaciones/<slug:clave>.<str:formato>', views.exportar_tabla, name='exportar_tabla'),
]
