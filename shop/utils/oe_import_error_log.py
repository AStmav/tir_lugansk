"""Формирование лога предупреждений/ошибок при импорте OE аналогов."""
from __future__ import annotations

from typing import List

CSV_HEADER = 'row;id_oe;id_tovar;id_brenb;reason'
DEFAULT_MAX_DETAIL_LINES = 500


class OeImportErrorCollector:
    """Собирает строки для error_log ImportFile без раздувания памяти на больших файлах."""

    def __init__(self, max_detail_lines: int = DEFAULT_MAX_DETAIL_LINES):
        self.max_detail_lines = max_detail_lines
        self.detail_lines: List[str] = []
        self.truncated_count = 0
        self.skipped_no_product = 0
        self.skipped_no_brand = 0
        self.skipped_empty = 0
        self.errors = 0

    def add_no_product(self, row: int, id_oe: str, id_tovar: str, id_brenb: str = '') -> None:
        self.skipped_no_product += 1
        self._append_detail(
            row, id_oe, id_tovar, id_brenb,
            'товар не найден (аналог сохранён без привязки)',
        )

    def add_no_brand(self, row: int, id_oe: str, id_tovar: str, id_brenb: str) -> None:
        self.skipped_no_brand += 1
        self._append_detail(row, id_oe, id_tovar, id_brenb, 'производитель не найден')

    def add_empty_fields(self, row: int, id_oe: str, id_tovar: str, reason: str) -> None:
        self.skipped_empty += 1
        self._append_detail(row, id_oe, id_tovar, '', reason)

    def add_processing_error(
        self,
        row: int,
        id_oe: str = '',
        id_tovar: str = '',
        id_brenb: str = '',
        reason: str = '',
    ) -> None:
        self.errors += 1
        self._append_detail(row, id_oe, id_tovar, id_brenb, reason or 'ошибка обработки')

    def add_batch_error(self, count: int, reason: str) -> None:
        self.errors += count
        if len(self.detail_lines) < self.max_detail_lines:
            self.detail_lines.append(f'0;;;batch;{reason} ({count} записей)')

    def _append_detail(
        self,
        row: int,
        id_oe: str,
        id_tovar: str,
        id_brenb: str,
        reason: str,
    ) -> None:
        if len(self.detail_lines) >= self.max_detail_lines:
            self.truncated_count += 1
            return
        self.detail_lines.append(
            f'{row};{id_oe};{id_tovar};{id_brenb};{reason}'
        )

    def build_log(self, *, created_count: int) -> str:
        """Текст для ImportFile.error_log."""
        lines = [
            '=== Сводка импорта OE аналогов ===',
            f'Создано аналогов: {created_count}',
            f'Без привязки к товару: {self.skipped_no_product}',
            f'Без производителя: {self.skipped_no_brand}',
            f'Пропущено (пустые поля): {self.skipped_empty}',
            f'Ошибки обработки: {self.errors}',
        ]
        if self.skipped_no_product:
            lines.append(
                'Подсказка: python manage.py link_oe_to_products — привязать аналоги к товарам'
            )
        if self.detail_lines:
            lines.extend(['', '=== Детали ===', CSV_HEADER, *self.detail_lines])
            if self.truncated_count:
                lines.append(
                    f'... и ещё {self.truncated_count} строк не показано (лимит {self.max_detail_lines})'
                )
        return '\n'.join(lines)
