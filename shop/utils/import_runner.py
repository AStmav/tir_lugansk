"""
Запуск импорта ImportFile отдельным процессом (не в потоке gunicorn).

Поток внутри воркера gunicorn обрывается при timeout/reload — статус «processing» зависает.
subprocess + start_new_session переживает перезапуск gunicorn.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import List, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

# Меньше пик RAM/PostgreSQL, чем 10000 (на prod падал postgres на первом bulk_update).
PRODUCTS_BATCH_SIZE = 2000
CSV_BATCH_SIZE = 5000


def build_import_command(import_file) -> List[str]:
    """Собирает argv для `python manage.py <command> ...`."""
    manage_py = os.path.join(settings.BASE_DIR, 'manage.py')
    file_path = import_file.file.path

    if import_file.is_dbf_file and import_file.file_type:
        from shop.dbf_schemas import DBF_SCHEMAS

        schema = DBF_SCHEMAS.get(import_file.file_type)
        if not schema:
            raise ValueError(f'Неизвестный тип файла: {import_file.file_type}')

        cmd = [sys.executable, manage_py, schema['command'], file_path]
        if import_file.file_type == 'products':
            cmd.extend([
                '--batch-size', str(PRODUCTS_BATCH_SIZE),
                '--disable-transactions',
                '--update-mode', import_file.update_mode or 'update',
            ])
        cmd.extend(['--import-file-id', str(import_file.id)])
        return cmd

    if import_file.is_dbf_file:
        file_name = os.path.basename(import_file.file.name).lower()
        if 'brend' in file_name:
            command_name = 'import_brands_dbf'
        elif 'oe_nomer' in file_name or 'oenomer' in file_name:
            command_name = 'import_oe_analogs_dbf'
        else:
            command_name = 'import_dbf'
        cmd = [sys.executable, manage_py, command_name, file_path]
        if command_name == 'import_dbf':
            cmd.extend([
                '--batch-size', str(PRODUCTS_BATCH_SIZE),
                '--disable-transactions',
                '--update-mode', import_file.update_mode or 'update',
            ])
        cmd.extend(['--import-file-id', str(import_file.id)])
        return cmd

    return [
        sys.executable, manage_py, 'import_products_new', file_path,
        '--batch-size', str(CSV_BATCH_SIZE),
        '--disable-transactions',
        '--import-file-id', str(import_file.id),
    ]


def launch_import_subprocess(import_file_id: int) -> Tuple[int, str]:
    """
    Запускает импорт в отдельном процессе. Возвращает (pid, путь к логу).
    """
    from shop.models import ImportFile

    import_file = ImportFile.objects.get(pk=import_file_id)
    if not import_file.file:
        raise FileNotFoundError('Файл импорта не загружен')
    file_path = getattr(import_file.file, 'path', None)
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f'Файл импорта не найден на диске: {file_path}')

    cmd = build_import_command(import_file)

    logs_dir = os.path.join(settings.BASE_DIR, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, f'import_admin_{import_file_id}.log')

    env = os.environ.copy()
    env.setdefault('DJANGO_SETTINGS_MODULE', os.environ.get(
        'DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings_prod'
    ))

    ImportFile.objects.filter(id=import_file_id).update(status='processing')

    log_file = open(log_path, 'a', encoding='utf-8')
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=settings.BASE_DIR,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except Exception:
        log_file.close()
        ImportFile.objects.filter(id=import_file_id).update(
            status='failed',
            error_log='Не удалось запустить subprocess импорта',
        )
        raise

    log_file.close()
    logger.info(
        'Import subprocess started pid=%s import_file_id=%s cmd=%s log=%s',
        proc.pid, import_file_id, ' '.join(cmd[2:4]), log_path,
    )
    return proc.pid, log_path
