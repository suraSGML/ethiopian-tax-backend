import os
from django.core.wsgi import get_wsgi_application

# Don't set a default - rely on environment variable from render.yaml
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    os.environ['DJANGO_SETTINGS_MODULE'] = 'tax_system.settings.production'
application = get_wsgi_application()
