"""
Синонимы и мягкая нормализация названия бренда из прайса.

Порядок в матчере не меняется: точное совпадение → синонимы → варианты написания.
"""
import re
from typing import Dict, List, Optional, Set

from shop.models import Brand


def normalize_brand_key(value: str) -> str:
    """Ключ для сравнения: lower, ё→е, без пробелов/дефисов/точек."""
    text = (value or '').strip().lower().replace('ё', 'е')
    return re.sub(r'[\s\-_\.]+', '', text)


def brand_text_variants(brand_text: str) -> List[str]:
    """Варианты написания для iexact-поиска по name/code."""
    text = (brand_text or '').strip()
    if not text:
        return []

    variants: List[str] = []
    seen: Set[str] = set()

    def add(value: str) -> None:
        value = (value or '').strip()
        if not value:
            return
        key = value.lower()
        if key in seen:
            return
        seen.add(key)
        variants.append(value)

    add(text)
    add(text.replace('-', ' '))
    add(text.replace('-', ''))
    add(re.sub(r'[\s\-_\.]+', ' ', text))
    add(re.sub(r'[\s\-_\.]+', '', text))
    return variants


def brands_from_aliases(brand_text: str) -> List[Brand]:
    """Бренды по таблице BrandAlias (без учёта регистра)."""
    from shop.models import BrandAlias

    text = (brand_text or '').strip()
    if not text:
        return []
    rows = (
        BrandAlias.objects.filter(alias__iexact=text)
        .select_related('brand')
        .order_by('id')
    )
    result: List[Brand] = []
    seen: Set[int] = set()
    for row in rows:
        if row.brand_id and row.brand_id not in seen:
            seen.add(row.brand_id)
            result.append(row.brand)
    return result


def build_normalized_brand_index() -> Dict[str, Brand]:
    """
    normalize_brand_key(name|code) → Brand.
    Если ключ неоднозначен (два бренда) — ключ не включаем.
    Строится один раз на импорт.
    """
    index: Dict[str, Brand] = {}
    ambiguous: Set[str] = set()
    for brand in Brand.objects.only('id', 'name', 'code').iterator(chunk_size=1000):
        for raw in (brand.name, brand.code):
            key = normalize_brand_key(raw or '')
            if not key or key in ambiguous:
                continue
            existing = index.get(key)
            if existing is None:
                index[key] = brand
            elif existing.id != brand.id:
                ambiguous.add(key)
                del index[key]
    return index


def brand_from_normalized_index(
    brand_text: str,
    index: Optional[Dict[str, Brand]],
) -> Optional[Brand]:
    if not index:
        return None
    key = normalize_brand_key(brand_text)
    if not key:
        return None
    return index.get(key)


def is_brand_section_header(matcher, article: str, brand_text: str) -> bool:
    """
    Строка-подзаголовок в прайсе: в колонке артикула только название производителя,
    колонка бренда пустая (CUMMINS / MAN / SCANIA …).
    """
    if (brand_text or '').strip():
        return False
    text = (article or '').strip()
    if not text:
        return False
    brands = matcher.resolve_brands(text)
    if len(brands) != 1:
        return False
    brand = brands[0]
    key = normalize_brand_key(text)
    if not key:
        return False
    for raw in (brand.name, brand.code):
        if key == normalize_brand_key(raw or ''):
            return True
    return False
