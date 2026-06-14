"""Утilities для списка брендов (каталог и страница /shop/brands/)."""
from collections import defaultdict

from django.conf import settings
from django.core.cache import cache

from .models import Brand


def brand_first_letter(name):
    first_char = (name or '').strip()[:1].upper()
    if not first_char:
        return '#'
    if ('A' <= first_char <= 'Z') or ('А' <= first_char <= 'Я') or first_char == 'Ё':
        return first_char
    return '#'


def group_brands_by_letter(brands):
    brand_groups_map = defaultdict(list)
    for brand in brands:
        brand_groups_map[brand_first_letter(brand.name)].append(brand)
    return sorted(
        brand_groups_map.items(),
        key=lambda item: (item[0] == '#', item[0]),
    )


def get_cached_all_brands():
    all_brands = cache.get('all_brands')
    if all_brands is None:
        all_brands = list(Brand.objects.all().order_by('name'))
        cache.set('all_brands', all_brands, settings.BRAND_CACHE_TIMEOUT)
    return all_brands
