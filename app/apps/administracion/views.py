from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.administracion.exportacion import (
    TABLAS_EXPORTABLES,
    exportar_tabla_csv,
    exportar_tabla_xlsx,
    resumen_tablas,
)
from apps.administracion.forms import UsuarioForm
from apps.administracion.permisos import GRUPO_ADMINISTRADORES, administrador_requerido


@administrador_requerido
def usuarios_list(request):
    q = request.GET.get('q', '').strip()
    usuarios = get_user_model().objects.prefetch_related('groups').order_by('username')
    if q:
        usuarios = usuarios.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    filas = [
        {
            'usuario': usuario,
            'es_administrador': usuario.is_superuser
            or any(grupo.name == GRUPO_ADMINISTRADORES for grupo in usuario.groups.all()),
        }
        for usuario in usuarios
    ]
    return render(request, 'administracion/usuarios_list.html', {'filas': filas, 'q': q})


@administrador_requerido
def usuario_create(request):
    form = UsuarioForm(request.POST or None, editor=request.user)
    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        messages.success(request, f'Usuario {usuario.username} creado correctamente.')
        return redirect('administracion:usuarios_list')
    return render(request, 'administracion/usuario_form.html', {'form': form, 'titulo': 'Nuevo usuario'})


@administrador_requerido
def usuario_update(request, pk):
    usuario = get_object_or_404(get_user_model(), pk=pk)
    form = UsuarioForm(request.POST or None, instance=usuario, editor=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Usuario {usuario.username} actualizado correctamente.')
        return redirect('administracion:usuarios_list')
    return render(
        request,
        'administracion/usuario_form.html',
        {'form': form, 'titulo': f'Editar usuario {usuario.username}', 'usuario_editado': usuario},
    )


@administrador_requerido
def exportaciones(request):
    return render(request, 'administracion/exportaciones.html', {'tablas': resumen_tablas()})


@administrador_requerido
def exportar_tabla(request, clave, formato):
    if clave not in TABLAS_EXPORTABLES:
        raise Http404
    if formato == 'csv':
        return exportar_tabla_csv(clave)
    if formato == 'xlsx':
        return exportar_tabla_xlsx(clave)
    raise Http404
