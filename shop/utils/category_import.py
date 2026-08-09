"""Сопоставление категорий при импорте номенклатуры по ID из 1С (SECTION_ID)."""
from __future__ import annotations

import re
from typing import Dict, Optional

from django.utils.text import slugify

from shop.models import Category

DESCRIPTION_SECTION_RE = re.compile(r'для\s+(\d+)', re.IGNORECASE)
SLUG_CATEGORY_RE = re.compile(r'^category-(\d+)$', re.IGNORECASE)
SLUG_SUFFIX_RE = re.compile(r'-(\d{6,})$')


def normalize_section_id(value) -> str:
    if value is None:
        return ''
    section_id = str(value).strip()
    section_id = section_id.replace('[', '').replace(']', '').replace(';', '').strip()
    return section_id


def extract_section_id_from_category(category) -> str:
    """Пытается извлечь SECTION_ID из описания или slug (для миграции/обслуживания)."""
    if category.description:
        match = DESCRIPTION_SECTION_RE.search(category.description)
        if match:
            return normalize_section_id(match.group(1))
    slug = (category.slug or '').strip()
    match = SLUG_CATEGORY_RE.match(slug)
    if match:
        return normalize_section_id(match.group(1))
    match = SLUG_SUFFIX_RE.search(slug)
    if match:
        return normalize_section_id(match.group(1))
    return ''


def ensure_unique_category_slug(base_slug: str, exclude_pk: Optional[int] = None) -> str:
    slug = base_slug or 'category'
    counter = 1
    while True:
        qs = Category.objects.filter(slug=slug)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return slug
        slug = f'{base_slug}-{counter}'
        counter += 1


def load_categories_by_section_id() -> Dict[str, Category]:
    return {
        cat.section_id: cat
        for cat in Category.objects.exclude(section_id__isnull=True).exclude(section_id='')
    }


def get_or_create_category_by_section_id(
    section_id,
    *,
    categories_cache: dict,
    by_section_id: dict,
    stats: Optional[dict] = None,
    stats_key: str = 'new_categories',
) -> Optional[Category]:
    """
    Находит категорию по section_id (1С). Slug/name можно менять в админке — связь не теряется.
    """
    section_id = normalize_section_id(section_id)
    if not section_id:
        return None

    if section_id in categories_cache:
        return categories_cache[section_id]

    category = by_section_id.get(section_id)
    if category is None:
        base_slug = slugify(f'category-{section_id}') or f'category-{section_id}'
        slug = ensure_unique_category_slug(base_slug)
        category, created = Category.objects.get_or_create(
            section_id=section_id,
            defaults={
                'slug': slug,
                'name': f'Категория {section_id}',
                'description': f'Автоматически созданная категория для {section_id}',
            },
        )
        if created and stats is not None:
            stats[stats_key] = stats.get(stats_key, 0) + 1

    categories_cache[section_id] = category
    by_section_id[section_id] = category
    return category
