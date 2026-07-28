import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
APP_DIR = PROJECT_ROOT / 'app'

for path in (PROJECT_ROOT, APP_DIR):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')

from django.core.wsgi import get_wsgi_application


application = get_wsgi_application()
