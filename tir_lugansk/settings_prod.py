"""
Production settings for tir_lugansk.
Использование: DJANGO_SETTINGS_MODULE=tir_lugansk.settings_prod

Путь к папке импорта изображений берётся из settings.py (INCOMING_IMAGES_DIR).
На сервере задайте свой каталог через .env: INCOMING_IMAGES_DIR=/var/www/tir-lugansk/incoming_images
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

# Админка доступна только при заходе по IP сервера (или localhost). По домену — 403.
ADMIN_ALLOWED_HOSTS = [
    '45.130.42.65',
    '127.0.0.1',
    'localhost',
]

CSRF_TRUSTED_ORIGINS = [
    'https://tir-lugansk.ru',
    'https://www.tir-lugansk.ru',
    'https://new.tir-lugansk.ru',
    'http://45.130.42.65',
    'http://localhost',
]

# HTTPS. Редирект HTTP→HTTPS делается в AllowHttpForAdminHostsMiddleware только для домена;
# по IP (45.130.42.65) админка доступна по HTTP, чтобы не требовать SSL для IP.
SECURE_SSL_REDIRECT = False
# Без Secure cookies админка по http://45.130.42.65/admin/ сможет сохранять сессию и CSRF.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
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

# --- Кеш (Redis через REDIS_URL) ---
# Если REDIS_URL задан, используем Redis как общий кэш для всех процессов.
# Если переменная не задана, остаётся кэш из settings.py (LocMem) — безопасный fallback.
_redis_url = os.environ.get('REDIS_URL', '').strip()
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _redis_url,
            'TIMEOUT': 300,
        }
    }

# --- БД ---
# DATABASES задаётся в settings.py (только PostgreSQL, переменные DB_* в .env).
