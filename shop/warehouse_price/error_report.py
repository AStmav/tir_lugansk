"""Разбор лога пропущенных строк импорта прайса."""
from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from django.conf import settings

# Сколько строк хранить в WarehousePriceImport.error_log (превью в админке).
ERROR_LOG_PREVIEW_MAX = 5000


def parse_error_log(error_log: str) -> List[Tuple[int, str, str, str]]:
    """Возвращает список (row, article, brand, reason)."""
    rows: List[Tuple[int, str, str, str]] = []
    if not error_log:
        return rows
    lines = error_log.strip().splitlines()
    for line in lines[1:]:
        if not line or line.startswith('...'):
            continue
        parts = line.split(';', 3)
        if len(parts) < 4:
            continue
        try:
            row_number = int(parts[0])
        except ValueError:
            row_number = 0
        rows.append((row_number, parts[1], parts[2], parts[3]))
    return rows


def summarize_skip_reasons(error_log: str) -> Dict[str, int]:
    """Счётчики причин пропуска для отчёта в админке."""
    counter: Counter = Counter()
    for *_rest, reason in parse_error_log(error_log):
        counter[reason or 'не указано'] += 1
    return dict(counter.most_common())


def summarize_missing_brands(error_log: str, *, limit: int = 30) -> List[Tuple[str, int]]:
    """
    Уникальные написания производителя из ошибок «производитель не найден».
    Возвращает [(brand_text, count), ...] по убыванию count.
    """
    counter: Counter = Counter()
    for _row, _article, brand, reason in parse_error_log(error_log):
        reason_l = (reason or '').lower()
        if 'производитель не найден' not in reason_l:
            continue
        label = (brand or '').strip() or '— (пусто)'
        counter[label] += 1
    return counter.most_common(limit)


def format_missing_brands_summary(error_log: str, *, limit: int = 30) -> str:
    rows = summarize_missing_brands(error_log, limit=limit)
    if not rows:
        return 'Ошибок «производитель не найден» нет.'
    lines = [f'{brand}: {count}' for brand, count in rows]
    total_unique = len(summarize_missing_brands(error_log, limit=10_000))
    if total_unique > limit:
        lines.append(f'… и ещё {total_unique - limit} написаний (полный CSV ниже)')
    return '\n'.join(lines)


def format_reasons_summary(error_log: str, *, limit: int = 20) -> str:
    summary = summarize_skip_reasons(error_log)
    if not summary:
        return 'Пропущенных строк нет.'
    lines = [f'{reason}: {count}' for reason, count in list(summary.items())[:limit]]
    if len(summary) > limit:
        lines.append(f'… и ещё {len(summary) - limit} типов причин')
    return '\n'.join(lines)


def preview_error_log(error_log: str, *, max_lines: int = 80) -> str:
    if not error_log:
        return ''
    lines = error_log.strip().splitlines()
    if len(lines) <= max_lines:
        return error_log.strip()
    head = lines[:max_lines]
    data_lines = max(len(lines) - 1, 0)
    tail_note = (
        f'\n… показаны первые {max_lines - 1} строк из {data_lines}. '
        f'Полный список — в файле «Скачать CSV с ошибками».'
    )
    return '\n'.join(head) + tail_note


def _error_row_line(err) -> str:
    return f'{err.row_number};{err.article};{err.brand};{err.reason}'


def format_error_log_csv(errors: Iterable, *, max_rows: int | None = None) -> str:
    """CSV row;article;brand;reason. max_rows=None — все строки."""
    errors_list = list(errors)
    if not errors_list:
        return ''
    lines = ['row;article;brand;reason']
    rows = errors_list if max_rows is None else errors_list[:max_rows]
    for err in rows:
        lines.append(_error_row_line(err))
    if max_rows is not None and len(errors_list) > max_rows:
        lines.append(f'... и ещё {len(errors_list) - max_rows} строк')
    return '\n'.join(lines)


def price_import_error_log_path(price_import_id: int) -> str:
    logs_dir = os.path.join(settings.BASE_DIR, 'logs')
    return os.path.join(logs_dir, f'price_import_{price_import_id}_errors.csv')


def write_price_import_error_log_file(price_import_id: int, errors: Iterable) -> str:
    """Полный CSV на диск (для скачивания из админки)."""
    path = price_import_error_log_path(price_import_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = format_error_log_csv(errors)
    Path(path).write_text(content, encoding='utf-8')
    return path


def read_price_import_error_log(price_import_id: int, fallback: str = '') -> str:
    """Полный лог с диска или усечённый из БД (старые импорты)."""
    path = price_import_error_log_path(price_import_id)
    if os.path.isfile(path):
        return Path(path).read_text(encoding='utf-8')
    return fallback
