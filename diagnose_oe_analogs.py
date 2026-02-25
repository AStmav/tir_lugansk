#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностика импорта OE аналогов
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import OeKod, Product

print("\n" + "=" * 70)
print("📊 ДИАГНОСТИКА OE АНАЛОГОВ")
print("=" * 70)

# 1. Общее количество аналогов в БД
total_analogs = OeKod.objects.count()
print(f"\n1️⃣ Всего аналогов в БД: {total_analogs:,}")

# 2. Аналоги с привязанными товарами
analogs_with_product = OeKod.objects.filter(product__isnull=False).count()
print(f"2️⃣ Аналогов с привязанными товарами: {analogs_with_product:,}")

# 3. Аналоги БЕЗ привязанных товаров
analogs_without_product = OeKod.objects.filter(product__isnull=True).count()
print(f"3️⃣ Аналогов БЕЗ товаров: {analogs_without_product:,}")

# 4. Уникальные товары с аналогами
products_with_analogs = Product.objects.filter(oe_analogs__isnull=False).distinct().count()
print(f"4️⃣ Товаров с аналогами: {products_with_analogs:,}")

# 5. Проверка на дубликаты по id_oe
from django.db.models import Count
duplicate_oe_ids = OeKod.objects.values('id_oe').annotate(
    count=Count('id_oe')
).filter(count__gt=1).count()
print(f"5️⃣ Дубликатов по id_oe: {duplicate_oe_ids}")

# 6. Статистика по брендам
analogs_with_brand = OeKod.objects.filter(brand__isnull=False).count()
analogs_without_brand = OeKod.objects.filter(brand__isnull=True).count()
print(f"6️⃣ Аналогов с брендом: {analogs_with_brand:,}")
print(f"   Аналогов без бренда: {analogs_without_brand:,}")

# 7. Примеры аналогов без товаров
print(f"\n📋 Примеры аналогов БЕЗ товаров (первые 10):")
analogs_no_product = OeKod.objects.filter(product__isnull=True)[:10]
for analog in analogs_no_product:
    print(f"   - ID_OE: {analog.id_oe}, NAME: {analog.name[:50]}, ID_TOVAR: {analog.id_tovar}")

# 8. Проверка товаров по id_tovar из аналогов
print(f"\n🔍 Проверка: сколько id_tovar из аналогов найдено в товарах:")
from django.db.models import Q
missing_products = OeKod.objects.filter(product__isnull=True).values_list('id_tovar', flat=True).distinct()
missing_count = Product.objects.filter(tmp_id__in=missing_products).count()
print(f"   Найдено товаров: {missing_count:,} из {len(missing_products):,} уникальных id_tovar")

# 9. Ожидаемое количество
expected = 439890
print(f"\n📊 СРАВНЕНИЕ:")
print(f"   Ожидалось в файле: {expected:,}")
print(f"   Импортировано в БД: {total_analogs:,}")
print(f"   Разница: {expected - total_analogs:,} ({((expected - total_analogs) / expected * 100):.1f}%)")
print(f"   Показывается на сайте: 42,652")
print(f"   Разница с БД: {total_analogs - 42652:,} ({((total_analogs - 42652) / total_analogs * 100):.1f}%)")

print("\n" + "=" * 70)
print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 70)

