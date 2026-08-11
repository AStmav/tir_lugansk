"""Слияние дубликатов категорий по SECTION_ID из 1С."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Count

from shop.models import Category, Product, SubCategory
from shop.utils.category_import import (
    extract_section_id_from_category,
    is_auto_import_category,
    normalize_section_id,
)


@dataclass
class OrphanAutoCategory:
    section_id: str
    category: Category
    products: int
    child_categories: int
    subcategories: int


@dataclass
class MapPlan:
    section_id: str
    target: Category
    orphan: Category
    products: int
    child_categories: int
    subcategories: int


def find_all_section_groups() -> Dict[str, List[Category]]:
    groups: Dict[str, List[Category]] = defaultdict(list)
    for category in Category.objects.all():
        key = category_section_key(category)
        if key:
            groups[key].append(category)
    return groups


def find_orphan_auto_categories() -> List[OrphanAutoCategory]:
    """
    Авто-категории без пары: merge их не трогает.
    Пример: «Категория 000022160» — единственная с таким SECTION_ID.
    """
    product_counts = dict(
        Product.objects.values('category_id')
        .annotate(cnt=Count('id'))
        .values_list('category_id', 'cnt')
    )
    orphans: List[OrphanAutoCategory] = []
    for section_id, categories in find_all_section_groups().items():
        if len(categories) != 1:
            continue
        category = categories[0]
        if not is_auto_import_category(category):
            continue
        orphans.append(
            OrphanAutoCategory(
                section_id=section_id,
                category=category,
                products=product_counts.get(category.pk, 0),
                child_categories=Category.objects.filter(parent_id=category.pk).count(),
                subcategories=SubCategory.objects.filter(parent_id=category.pk).count(),
            )
        )
    return sorted(orphans, key=lambda item: item.section_id)


def find_auto_category_for_section(section_id: str, *, exclude_pk: Optional[int] = None) -> Optional[Category]:
    section_id = normalize_section_id(section_id)
    if not section_id:
        return None

    by_field = Category.objects.filter(section_id=section_id)
    if exclude_pk:
        by_field = by_field.exclude(pk=exclude_pk)
    for category in by_field:
        if is_auto_import_category(category):
            return category

    for category in Category.objects.all():
        if exclude_pk and category.pk == exclude_pk:
            continue
        if is_auto_import_category(category) and category_section_key(category) == section_id:
            return category
    return None


def build_map_plan(section_id: str, target_slug: str) -> MapPlan:
    section_id = normalize_section_id(section_id)
    target = Category.objects.get(slug=target_slug)
    orphan = find_auto_category_for_section(section_id, exclude_pk=target.pk)
    if orphan is None:
        raise Category.DoesNotExist(
            f'Авто-категория для SECTION_ID {section_id} не найдена'
        )
    if target.section_id and normalize_section_id(target.section_id) != section_id:
        raise ValueError(
            f'Категория {target_slug} уже привязана к SECTION_ID {target.section_id}, '
            f'ожидался {section_id}'
        )
    return MapPlan(
        section_id=section_id,
        target=target,
        orphan=orphan,
        products=Product.objects.filter(category_id=orphan.pk).count(),
        child_categories=Category.objects.filter(parent_id=orphan.pk).exclude(pk=target.pk).count(),
        subcategories=SubCategory.objects.filter(parent_id=orphan.pk).count(),
    )


def map_orphan_auto_category(section_id: str, target_slug: str, *, dry_run: bool = False) -> MapPlan:
    """Привязать SECTION_ID к нормальной категории и слить авто-дубликат."""
    plan = build_map_plan(section_id, target_slug)
    if dry_run:
        return plan

    target = Category.objects.get(pk=plan.target.pk)
    orphan = Category.objects.get(pk=plan.orphan.pk)
    if not target.section_id:
        Category.objects.filter(pk=target.pk).update(section_id=plan.section_id)
        target.section_id = plan.section_id
    merge_duplicate_into_canonical(target, orphan)
    return plan


def cleanup_orphan_auto_categories(
    *,
    dry_run: bool = False,
    delete_empty: bool = False,
    deactivate: bool = False,
) -> dict:
    orphans = find_orphan_auto_categories()
    totals = {
        'orphans': len(orphans),
        'deleted': 0,
        'deactivated': 0,
    }
    if dry_run or not orphans:
        return totals

    with transaction.atomic():
        for item in orphans:
            category = Category.objects.get(pk=item.category.pk)
            if delete_empty and item.products == 0 and item.child_categories == 0 and item.subcategories == 0:
                category.delete()
                totals['deleted'] += 1
            elif deactivate:
                Category.objects.filter(pk=category.pk).update(is_active=False)
                totals['deactivated'] += 1
    return totals


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
