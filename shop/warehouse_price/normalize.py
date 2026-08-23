import re
from decimal import Decimal, InvalidOperation
from typing import Optional


def parse_price(value) -> Optional[Decimal]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in ('—', '-', '–'):
        return None
    text = text.replace(' ', '').replace('\u00a0', '')
    text = text.replace(',', '.')
    text = re.sub(r'[^\d.]', '', text)
    if not text:
        return None
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if amount < 0:
        return None
    return amount.quantize(Decimal('0.01'))


def parse_quantity(value) -> int:
    """
    Остаток из прайса → целое число штук.

    «4.000» / «4,000» (дробный формат из Excel/CSV) → 4, не 4000.
    Числа Excel (int/float) берём напрямую, без str(4.0) → «40».
    """
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        if value != value:  # NaN
            return 0
        return max(0, int(value))
    if isinstance(value, Decimal):
        return max(0, int(value))

    text = str(value).strip()
    if not text or text in ('—', '-', '–', '+', '++'):
        return 0
    text = text.replace(' ', '').replace('\u00a0', '')
    text = text.replace(',', '.')
    text = re.sub(r'[^\d.]', '', text)
    if not text or text == '.':
        return 0
    try:
        qty = int(Decimal(text))
    except (InvalidOperation, ValueError, OverflowError):
        return 0
    return max(0, qty)


def cell_to_str(value) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and value == value and value == int(value):
        return str(int(value))
    return str(value).strip()
