"""Слияние дубликатов категорий по SECTION_ID из 1С."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Count

from shop.models import Category, Product, SubCategory
from shop.utils.category_import import extract_section_id_from_category, normalize_section_id


@dataclass
class MergePlan:
    section_id: str
    canonical: Category
    duplicate: Category
    products: int
    child_categories: int
    subcategories: int

    @property
    def total_moved(self) -> int:
        return self.products + self.child_categories + self.subcategories


def category_section_key(category: Category) -> str:
    """Ключ группировки: section_id в БД или извлечённый из slug/description."""
    if category.section_id:
        return normalize_section_id(category.section_id)
    return extract_section_id_from_category(category)


def _is_auto_category_name(name: str) -> bool:
    return (name or '').strip().startswith('Категория ')


def pick_canonical(categories: List[Category], product_counts: Dict[int, int]) -> Category:
    """Выбирает «главную» категорию в группе дубликатов."""

    def sort_key(cat: Category) -> Tuple:
        return (
            0 if cat.section_id else 1,
            1 if _is_auto_category_name(cat.name) else 0,
            -(product_counts.get(cat.pk, 0)),
            cat.pk,
        )

    return min(categories, key=sort_key)


def find_duplicate_groups() -> Dict[str, List[Category]]:
    """Группы категорий с одинаковым section_id (2+ записей)."""
    categories = list(Category.objects.all())
    product_counts = dict(
        Product.objects.values('category_id')
        .annotate(cnt=Count('id'))
        .values_list('category_id', 'cnt')
    )

    groups: Dict[str, List[Category]] = defaultdict(list)
    for category in categories:
        key = category_section_key(category)
        if key:
            groups[key].append(category)

    return {
        key: cats
        for key, cats in groups.items()
        if len(cats) > 1
    }


def build_merge_plans(groups: Optional[Dict[str, List[Category]]] = None) -> List[MergePlan]:
    if groups is None:
        groups = find_duplicate_groups()

    product_counts = dict(
        Product.objects.values('category_id')
        .annotate(cnt=Count('id'))
        .values_list('category_id', 'cnt')
    )

    plans: List[MergePlan] = []
    for section_id, categories in sorted(groups.items()):
        canonical = pick_canonical(categories, product_counts)
        for duplicate in categories:
            if duplicate.pk == canonical.pk:
                continue
            plans.append(
                MergePlan(
                    section_id=section_id,
                    canonical=canonical,
                    duplicate=duplicate,
                    products=product_counts.get(duplicate.pk, 0),
                    child_categories=Category.objects.filter(parent_id=duplicate.pk)
                    .exclude(pk=canonical.pk)
                    .count(),
                    subcategories=SubCategory.objects.filter(parent_id=duplicate.pk).count(),
                )
            )
    return plans


def merge_duplicate_into_canonical(canonical: Category, duplicate: Category) -> dict:
    """Переносит связи с duplicate на canonical и удаляет duplicate."""
    stats = {
        'products': 0,
        'child_categories': 0,
        'subcategories': 0,
    }

    if canonical.pk == duplicate.pk:
        return stats

    if canonical.parent_id == duplicate.pk:
        Category.objects.filter(pk=canonical.pk).update(parent_id=duplicate.parent_id)
        canonical.parent_id = duplicate.parent_id

    stats['products'] = Product.objects.filter(category_id=duplicate.pk).update(
        category_id=canonical.pk
    )
    stats['child_categories'] = Category.objects.filter(parent_id=duplicate.pk).exclude(
        pk=canonical.pk
    ).update(parent_id=canonical.pk)
    stats['subcategories'] = SubCategory.objects.filter(parent_id=duplicate.pk).update(
        parent_id=canonical.pk
    )

    if not canonical.section_id and duplicate.section_id:
        Category.objects.filter(pk=canonical.pk).update(section_id=duplicate.section_id)
        canonical.section_id = duplicate.section_id

    duplicate.delete()
    return stats


def merge_all_duplicates(*, dry_run: bool = False) -> Tuple[List[MergePlan], dict]:
    """
    Находит и сливает дубликаты. При dry_run только строит план.
    Возвращает (plans, totals).
    """
    plans = build_merge_plans()
    totals = {
        'groups': len({p.section_id for p in plans}),
        'merged': 0,
        'products': 0,
        'child_categories': 0,
        'subcategories': 0,
    }

    if dry_run or not plans:
        return plans, totals

    with transaction.atomic():
        for plan in plans:
            if not Category.objects.filter(pk=plan.duplicate.pk).exists():
                continue
            canonical = Category.objects.get(pk=plan.canonical.pk)
            duplicate = Category.objects.get(pk=plan.duplicate.pk)
            stats = merge_duplicate_into_canonical(canonical, duplicate)
            totals['merged'] += 1
            totals['products'] += stats['products']
            totals['child_categories'] += stats['child_categories']
            totals['subcategories'] += stats['subcategories']

    return plans, totals
