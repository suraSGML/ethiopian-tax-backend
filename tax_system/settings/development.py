from .base import *

DEBUG = True

# ─── Database: Supabase PostgreSQL ────────────────────────────────────────────
# Reads from .env file. Copy .env.example → .env and fill in your Supabase creds.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',   # works with both psycopg2 and psycopg3
        'NAME': config('DB_NAME', default='postgres'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'sslmode': 'require',
            'options': '-c search_path=public',
        },
        'CONN_MAX_AGE': 60,
    }
}

# ─── Cache: local memory (no Redis needed for dev) ────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# ─── Email: print to console in dev ───────────────────────────────────────────
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
)

# ─── Celery: run tasks synchronously in dev (no Redis needed) ─────────────────
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ─── Axes: relax lockout in dev ───────────────────────────────────────────────
AXES_ENABLED = False   # Turn off brute-force lockout during development

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '[%(levelname)s] %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django.db.backends': {'handlers': ['console'], 'level': 'WARNING'},
    },
}
