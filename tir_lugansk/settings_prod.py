"""
Production settings for tir_lugansk.
Использование: DJANGO_SETTINGS_MODULE=tir_lugansk.settings_prod
"""
import os

from .settings import *  # noqa: F401, F403

# --- Безопасность ---
DEBUG = False

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'CHANGE_ME_GENERATE_WITH: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
)

ALLOWED_HOSTS = [
    'tir-lugansk.ru',
    'www.tir-lugansk.ru',
    'new.tir-lugansk.ru',
    '45.130.42.65',
    'localhost',
    '127.0.0.1',
]

CSRF_TRUSTED_ORIGINS = [
    'https://tir-lugansk.ru',
    'https://www.tir-lugansk.ru',
    'https://new.tir-lugansk.ru',
    'http://45.130.42.65',
    'http://localhost',
]

# HTTPS (раскомментировать после настройки SSL)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'


SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# --- Логирование ---
# Путь к логам относительно BASE_DIR (из .settings)
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(LOGS_DIR / 'django.log'),
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'shop': {
            'handlers': ['console', 'file'],
            'level': 'INFO',  # В продакшене без DEBUG-логов
            'propagate': False,
        },
    },
}

# --- Кеш (опционально: Redis) ---
# Раскомментировать после установки Redis и pip install redis:
# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.redis.RedisCache',
#         'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
#         'TIMEOUT': 300,
#         'OPTIONS': {'MAX_ENTRIES': 1000},
#     }
# }

# --- БД PostgreSQL (опционально) ---
# Раскомментировать при переходе с SQLite:
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.environ.get('DB_NAME', 'tir_lugansk'),
#         'USER': os.environ.get('DB_USER', 'tir_db'),
#         'PASSWORD': os.environ.get('DB_PASSWORD', ''),
#         'HOST': os.environ.get('DB_HOST', 'localhost'),
#         'PORT': os.environ.get('DB_PORT', '5432'),
#         'CONN_MAX_AGE': 60,
#         'OPTIONS': {'sslmode': 'disable'},
#     }
# }
