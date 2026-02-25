#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностика: Почему товары не находятся для аналогов БЕЗ товаров?
"""

import os
import django
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import OeKod, Product

print("\n" + "=" * 70)
print("🔍 ДИАГНОСТИКА: Почему товары не находятся?")
print("=" * 70)

# 1. Находим аналоги без товаров
analogs_without_product = OeKod.objects.filter(product__isnull=True)
total = analogs_without_product.count()

print(f"\n1️⃣ Аналогов БЕЗ товаров: {total:,}")

if total == 0:
    print("✅ Все аналоги уже связаны с товарами!")
    exit()

# 2. Проверяем первые 10 примеров
print(f"\n2️⃣ Примеры аналогов БЕЗ товаров (первые 10):")
print("=" * 70)

sample_analogs = analogs_without_product[:10]
found_count = 0
not_found_count = 0

# Загружаем товары в кэш (как в команде)
products_by_tmp_id = {}
products_by_clean_tmp_id = {}

for product in Product.objects.only('id', 'tmp_id').iterator(chunk_size=5000):
    if product.tmp_id:
        products_by_tmp_id[product.tmp_id] = product.id
        clean_tmp_id = re.sub(r'-dup\d+$', '', product.tmp_id)
        if clean_tmp_id != product.tmp_id:
            products_by_clean_tmp_id[clean_tmp_id] = product.id

print(f"\n   Загружено товаров в кэш: {len(products_by_tmp_id):,}")

for i, analog in enumerate(sample_analogs, 1):
    print(f"\n   {i}. Аналог:")
    print(f"      ID_OE: {analog.id_oe}")
    print(f"      ID_TOVAR: {analog.id_tovar}")
    print(f"      OE код: {analog.oe_kod}")
    
    if not analog.id_tovar:
        print(f"      ⚠️ ID_TOVAR пустой!")
        not_found_count += 1
        continue
    
    # Ищем товар
    product_id = products_by_tmp_id.get(analog.id_tovar)
    
    if not product_id:
        clean_id_tovar = re.sub(r'-dup\d+$', '', analog.id_tovar)
        product_id = products_by_clean_tmp_id.get(clean_id_tovar)
    
    if product_id:
        product = Product.objects.get(id=product_id)
        print(f"      ✅ Товар найден: {product.name[:60]}")
        print(f"         TMP_ID: {product.tmp_id}")
        found_count += 1
    else:
        print(f"      ❌ Товар НЕ найден")
        print(f"         Искали: '{analog.id_tovar}'")
        clean_id_tovar = re.sub(r'-dup\d+$', '', analog.id_tovar)
        print(f"         Очищенный: '{clean_id_tovar}'")
        
        # Проверяем, есть ли похожие товары
        similar = Product.objects.filter(tmp_id__startswith=analog.id_tovar[:10]).first()
        if similar:
            print(f"         Похожий товар: {similar.tmp_id}")
        
        not_found_count += 1

# 3. Статистика по всем аналогам
print(f"\n" + "=" * 70)
print("3️⃣ СТАТИСТИКА ПО ВСЕМ АНАЛОГАМ")
print("=" * 70)

all_id_tovar = list(analogs_without_product.values_list('id_tovar', flat=True).distinct())
print(f"\n   Уникальных ID_TOVAR: {len(all_id_tovar):,}")

# Проверяем, сколько из них найдено
found_id_tovar = 0
not_found_id_tovar = 0

for id_tovar in all_id_tovar[:100]:  # Проверяем первые 100 для скорости
    if not id_tovar:
        continue
    
    product_id = products_by_tmp_id.get(id_tovar)
    if not product_id:
        clean_id_tovar = re.sub(r'-dup\d+$', '', id_tovar)
        product_id = products_by_clean_tmp_id.get(clean_id_tovar)
    
    if product_id:
        found_id_tovar += 1
    else:
        not_found_id_tovar += 1

print(f"   Из первых 100 ID_TOVAR:")
print(f"      Найдено товаров: {found_id_tovar}")
print(f"      НЕ найдено: {not_found_id_tovar}")

# 4. Вывод
print(f"\n" + "=" * 70)
print("📊 ВЫВОД")
print("=" * 70)

if found_count > 0:
    print(f"\n✅ Некоторые товары НАЙДЕНЫ!")
    print(f"   Команда link_oe_to_products должна работать после исправления.")
else:
    print(f"\n⚠️ Товары НЕ найдены ни для одного примера.")
    print(f"   Возможные причины:")
    print(f"   1. Товары действительно отсутствуют в базе")
    print(f"   2. ID_TOVAR в аналогах не совпадает с TMP_ID в товарах")
    print(f"   3. Проблема с форматом данных (пробелы, регистр)")

print(f"\n💡 РЕКОМЕНДАЦИЯ:")
print(f"   Запустите команду link_oe_to_products снова после исправления.")
print(f"   Команда теперь учитывает суффиксы -dupN.")

print("\n" + "=" * 70)

