"""
Варианты артикула с учётом приставок производителя.

Заказчик: SE-M → SEM7838 и 7838; Auger → AUG… и т.д.
"""
from typing import List, Optional, Set

from shop.models import Brand, Product

# Запасной список по имени бренда, если в БД ещё нет BrandArticlePrefix
DEFAULT_PREFIXES_BY_BRAND_NAME = {
    'se-m': ['SEM'],
    'sem': ['SEM'],
    'auger': ['AUG'],
    'universal components': ['UCA'],
    'm-filter': ['MFA', 'MF'],
    'mfilter': ['MFA', 'MF'],
    'lema': ['LE'],
    'dinex': ['DIN'],
}


def _normalize_prefix(prefix: str) -> str:
    return Product.clean_number(prefix)


def get_prefixes_for_brand(brand: Optional[Brand]) -> List[str]:
    if not brand:
        return []
    from shop.models import BrandArticlePrefix

    db_prefixes = list(
        BrandArticlePrefix.objects.filter(brand=brand).values_list('prefix', flat=True)
    )
    result: List[str] = []
    seen: Set[str] = set()
    for raw in db_prefixes:
        cleaned = _normalize_prefix(raw)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    if result:
        return result

    name = (brand.name or '').strip().lower()
    for key, prefixes in DEFAULT_PREFIXES_BY_BRAND_NAME.items():
        if name == key:
            for raw in prefixes:
                cleaned = _normalize_prefix(raw)
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    result.append(cleaned)
            break
    return result


def article_variants(brand: Optional[Brand], article: str) -> List[str]:
    """
    Уникальный список очищенных вариантов артикула:
    как в прайсе + без приставки + с приставкой бренда.
    """
    clean = Product.clean_number(article)
    if not clean:
        return []

    variants: List[str] = [clean]
    seen: Set[str] = {clean}

    def add(value: str) -> None:
        if value and value not in seen:
            seen.add(value)
            variants.append(value)

    for prefix in get_prefixes_for_brand(brand):
        if clean.startswith(prefix) and len(clean) > len(prefix):
            add(clean[len(prefix):])
        else:
            add(prefix + clean)

    return variants
