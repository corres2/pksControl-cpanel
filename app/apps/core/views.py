import os
import subprocess

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.shortcuts import render
from django.utils import timezone

from apps.core.models import InstallationStatus


@login_required
def home(request):
    return render(request, 'core/home.html', {'app_version': settings.APP_VERSION})


def _get_database_status():
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return 'Error'
    return 'OK'


def _get_latest_installation_status():
    try:
        return InstallationStatus.objects.order_by('-updated_at').first()
    except Exception:
        return None


def _get_git_commit(installation_status):
    if installation_status and installation_status.git_commit:
        return installation_status.git_commit

    env_commit = os.environ.get('GIT_COMMIT')
    if env_commit:
        return env_commit

    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=settings.ROOT_DIR,
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return 'No disponible'

    return result.stdout.strip() or 'No disponible'


@login_required
def system_status(request):
    installation_status = _get_latest_installation_status()
    context = {
        'server_name': settings.SERVER_NAME,
        'app_version': settings.APP_VERSION,
        'debug': settings.DEBUG,
        'database_status': _get_database_status(),
        'server_time': timezone.localtime(timezone.now()),
        'installation_status': installation_status,
        'git_commit': _get_git_commit(installation_status),
    }
    return render(request, 'core/status.html', context)
