from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

GRUPO_ADMINISTRADORES = 'Administradores'


def es_administrador(usuario):
    if not getattr(usuario, 'is_authenticated', False):
        return False
    if usuario.is_superuser:
        return True
    return usuario.groups.filter(name=GRUPO_ADMINISTRADORES).exists()


def administrador_requerido(vista):
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not es_administrador(request.user):
            raise PermissionDenied
        return vista(request, *args, **kwargs)

    return envoltura


def contexto_administrador(request):
    return {'es_administrador': es_administrador(getattr(request, 'user', None))}
