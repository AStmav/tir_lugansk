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
    if value is None:
        return 0
    text = str(value).strip()
    if not text or text in ('—', '-', '–', '+', '++'):
        return 0
    text = text.replace(' ', '').replace('\u00a0', '')
    text = re.sub(r'[^\d]', '', text)
    if not text:
        return 0
    try:
        qty = int(text)
    except ValueError:
        return 0
    return max(0, qty)


def cell_to_str(value) -> str:
    if value is None:
        return ''
    return str(value).strip()
