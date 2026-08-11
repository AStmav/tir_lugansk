"""Разбор лога пропущенных строк импорта прайса."""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Tuple


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
    tail_note = f'\n… показаны первые {max_lines - 1} строк из {len(lines) - 1}. Скачайте полный отчёт (CSV).'
    return '\n'.join(head) + tail_note
