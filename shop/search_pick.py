"""Группировка товаров при точном выборе из подсказки поиска (search_pick)."""
from django.db.models import Q

from .models import Product


def expand_product_group(base_queryset, seed_product_ids):
    """
    По выбранному товару (или набору) находит все товары с теми же
    нормализованными значениями artikyl_number_clean, catalog_number_clean и cross_number.

    Используется при search_pick: пользователь выбрал конкретную строку подсказки,
    нужно показать всю группу «одинаковых» по кросс-коду и дополнительному номеру,
    а не широкий поиск по части значения.
    """
    seed_ids = {pid for pid in seed_product_ids if pid}
    if not seed_ids:
        return set()

    seeds = base_queryset.filter(id__in=seed_ids)
    if not seeds.exists():
        return set()

    found_artikyl_clean_values = set()
    found_catalog_clean_values = set()
    found_catalog_numbers = set()
    found_cross_numbers = set()

    artikyl_clean_data = seeds.values_list('artikyl_number_clean', flat=True)
    for artikyl_number_clean in artikyl_clean_data:
        if artikyl_number_clean:
            found_artikyl_clean_values.add(artikyl_number_clean)

    catalog_clean_data = seeds.values_list('catalog_number_clean', flat=True)
    for catalog_number_clean in catalog_clean_data:
        if catalog_number_clean:
            found_catalog_clean_values.add(catalog_number_clean)

    catalog_data = seeds.values_list('catalog_number', 'catalog_number_clean', flat=False)
    for catalog_number, catalog_number_clean in catalog_data:
        if catalog_number:
            found_catalog_numbers.add(catalog_number)
        if catalog_number_clean:
            found_catalog_numbers.add(catalog_number_clean)

    cross_data = seeds.values_list('cross_number', flat=True)
    for cross_number in cross_data:
        if cross_number and cross_number.strip():
            found_cross_numbers.add(cross_number.strip())

    grouped_ids = set(seed_ids)

    if found_artikyl_clean_values:
        grouped_ids.update(
            base_queryset.filter(
                artikyl_number_clean__in=found_artikyl_clean_values
            ).values_list('id', flat=True)
        )

    if found_catalog_clean_values:
        grouped_ids.update(
            base_queryset.filter(
                catalog_number_clean__in=found_catalog_clean_values
            ).values_list('id', flat=True)
        )

    if found_catalog_numbers:
        catalog_query = Q()
        for cat_num in found_catalog_numbers:
            catalog_query |= Q(catalog_number__iexact=cat_num)
            if '.' in cat_num:
                catalog_query |= Q(catalog_number__iexact=cat_num.replace('.', ''))
            elif len(cat_num) >= 4:
                catalog_query |= Q(catalog_number__iexact=cat_num[:3] + '.' + cat_num[3:])

        grouped_ids.update(
            base_queryset.filter(catalog_query).values_list('id', flat=True)
        )

    if found_cross_numbers:
        grouped_ids.update(
            base_queryset.filter(
                cross_number__in=found_cross_numbers
            ).exclude(cross_number='').values_list('id', flat=True)
        )

    return grouped_ids
