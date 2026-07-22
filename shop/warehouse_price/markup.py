"""Наценка склада на цену из прайса."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

from shop.models import Warehouse


class MarkupError(ValueError):
    """Цена не попала в настроенные диапазоны."""


def _as_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def resolve_markup_percent(warehouse: Warehouse, cost_price) -> Decimal:
    """Возвращает процент наценки для цены закупа (из файла)."""
    cost = _as_decimal(cost_price)
    mode = warehouse.markup_mode or Warehouse.MARKUP_NONE

    if mode == Warehouse.MARKUP_NONE:
        return Decimal('0')

    if mode == Warehouse.MARKUP_PERCENT:
        return _as_decimal(warehouse.markup_percent or 0)

    if mode == Warehouse.MARKUP_RANGES:
        for row in warehouse.markup_ranges.all():
            low = _as_decimal(row.price_from)
            if cost < low:
                continue
            if row.price_to is not None and cost > _as_decimal(row.price_to):
                continue
            return _as_decimal(row.percent)
        raise MarkupError(
            f'цена {cost} не входит ни в один диапазон наценки склада'
        )

    return Decimal('0')


def apply_markup(warehouse: Warehouse, cost_price) -> Decimal:
    """
    Цена для витрины = цена прайса × (1 + percent/100).
    Округление до копеек (HALF_UP).
    """
    cost = _as_decimal(cost_price)
    percent = resolve_markup_percent(warehouse, cost)
    if percent == 0:
        return cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    sell = cost * (Decimal('1') + percent / Decimal('100'))
    return sell.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def try_apply_markup(warehouse: Warehouse, cost_price) -> Tuple[Optional[Decimal], str]:
    """Как apply_markup, но без исключения: (price, error_reason)."""
    try:
        return apply_markup(warehouse, cost_price), ''
    except MarkupError as exc:
        return None, str(exc)
