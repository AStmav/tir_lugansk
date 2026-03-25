#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

# Загружаем .env до выбора settings (как в tir_lugansk/settings.py)
try:
    from dotenv import load_dotenv
    _base = Path(__file__).resolve().parent
    _env = _base / 'tir_lugansk' / '.env'
    if not _env.exists():
        _env = _base / '.env'
    load_dotenv(_env)
except ImportError:
    pass

def main():
    """Run administrative tasks."""
    # По умолчанию — разработка (tir_lugansk.settings).
    # Продакшен: задайте в окружении сервера DJANGO_SETTINGS_MODULE=tir_lugansk.settings_prod
    # или в .env: DJANGO_SETTINGS_MODULE=tir_lugansk.settings_prod
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main() 