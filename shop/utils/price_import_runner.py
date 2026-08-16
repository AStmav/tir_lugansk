"""
Фоновый импорт прайса склада (отдельный subprocess, не HTTP gunicorn).

По аналогии с shop.utils.import_runner для ImportFile.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import List, Tuple

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def warehouse_has_running_price_import(warehouse_id: int, exclude_id: int = None) -> bool:
    from shop.models import WarehousePriceImport

    qs = WarehousePriceImport.objects.filter(
        warehouse_id=warehouse_id,
        status=WarehousePriceImport.STATUS_PROCESSING,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def build_price_import_command(price_import_id: int) -> List[str]:
    manage_py = os.path.join(settings.BASE_DIR, 'manage.py')
    return [
        sys.executable,
        manage_py,
        'import_warehouse_price',
        '--price-import-id',
        str(price_import_id),
    ]


def launch_price_import_subprocess(price_import_id: int) -> Tuple[int, str]:
    """
    Запускает import_warehouse_price в отдельном процессе.
    Возвращает (pid, путь к логу).
    """
    from shop.models import WarehousePriceImport

    price_import = WarehousePriceImport.objects.select_related('warehouse').get(pk=price_import_id)
    if not price_import.file:
        raise FileNotFoundError('Файл прайса не загружен')
    file_path = getattr(price_import.file, 'path', None)
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f'Файл прайса не найден на диске: {file_path}')

    if warehouse_has_running_price_import(
        price_import.warehouse_id,
        exclude_id=price_import_id,
    ):
        raise RuntimeError(
            f'У склада «{price_import.warehouse.name_internal}» уже выполняется импорт прайса'
        )

    cmd = build_price_import_command(price_import_id)

    logs_dir = os.path.join(settings.BASE_DIR, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, f'price_import_{price_import_id}.log')

    env = os.environ.copy()
    env.setdefault(
        'DJANGO_SETTINGS_MODULE',
        os.environ.get('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings_prod'),
    )

    WarehousePriceImport.objects.filter(pk=price_import_id).update(
        status=WarehousePriceImport.STATUS_PROCESSING,
        started_at=timezone.now(),
        processed_rows=0,
    )

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
        WarehousePriceImport.objects.filter(pk=price_import_id).update(
            status=WarehousePriceImport.STATUS_FAILED,
            summary='Не удалось запустить subprocess импорта прайса',
            processed_at=timezone.now(),
        )
        raise

    log_file.close()
    logger.info(
        'Price import subprocess started pid=%s price_import_id=%s log=%s',
        proc.pid,
        price_import_id,
        log_path,
    )
    return proc.pid, log_path
