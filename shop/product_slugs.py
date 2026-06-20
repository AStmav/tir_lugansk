"""
Генерация человекочитаемых slug для карточек товаров.

Формат: артикул-бренд-короткое-название (транслит).
Пример: ns03-g2-auger-shtucer-topl-trubki
"""
from django.utils.text import slugify

try:
    from unidecode import unidecode
except ImportError:  # pragma: no cover
    def unidecode(text):
        return text

MAX_SLUG_LEN = 200
NAME_PART_MAX = 40


def slug_part(text, *, max_len=None):
    """Транслит + slugify; пустая строка, если не осталось символов."""
    raw = unidecode((text or '').strip())
    part = slugify(raw, allow_unicode=False)
    if not part:
        return ''
    if max_len and len(part) > max_len:
        part = part[:max_len].rstrip('-')
    return part


def build_product_slug(catalog_number, brand_name, product_name):
    """
    Собирает slug: каталожный номер, бренд, укороченное название.
    Дублирующиеся части не повторяются.
    """
    parts = []
    for value, limit in (
        (catalog_number, None),
        (brand_name, None),
        (product_name, NAME_PART_MAX),
    ):
        part = slug_part(value, max_len=limit)
        if part and part not in parts:
            parts.append(part)
    base = '-'.join(parts) if parts else 'product'
    return base[:MAX_SLUG_LEN]


def uniquify_slug(base_slug, is_taken, *, max_suffix=99):
    """
    Возвращает base_slug или base_slug-2, base_slug-3, … если slug занят.
    is_taken(slug) → bool.
    """
    base_slug = (base_slug or 'product')[:MAX_SLUG_LEN].strip('-') or 'product'
    if not is_taken(base_slug):
        return base_slug

    for suffix in range(2, max_suffix + 2):
        tail = f'-{suffix}'
        room = MAX_SLUG_LEN - len(tail)
        candidate = f'{base_slug[:room]}{tail}'
        if not is_taken(candidate):
            return candidate

    raise ValueError(f'Не удалось подобрать уникальный slug для {base_slug!r}')


def make_product_slug(catalog_number, brand_name, product_name, is_taken):
    """Готовый slug с проверкой уникальности."""
    return uniquify_slug(
        build_product_slug(catalog_number, brand_name, product_name),
        is_taken,
    )
