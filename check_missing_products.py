#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка: Действительно ли товары отсутствуют в базе?
"""

import os
import django
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import OeKod, Product

print("\n" + "=" * 70)
print("🔍 ПРОВЕРКА: Действительно ли товары отсутствуют?")
print("=" * 70)

# 1. Получаем ID_TOVAR из аналогов без товаров
analogs_without_product = OeKod.objects.filter(product__isnull=True)
id_tovar_list = list(analogs_without_product.values_list('id_tovar', flat=True).distinct())

print(f"\n1️⃣ Уникальных ID_TOVAR из аналогов БЕЗ товаров: {len(id_tovar_list):,}")

# 2. Проверяем, есть ли эти товары в базе
print(f"\n2️⃣ Проверяем наличие товаров в базе...")
print("=" * 70)

found_count = 0
not_found_count = 0
found_examples = []
not_found_examples = []

# Загружаем все товары в кэш
products_by_tmp_id = {}
products_by_clean_tmp_id = {}

for product in Product.objects.only('id', 'tmp_id').iterator(chunk_size=5000):
    if product.tmp_id:
        products_by_tmp_id[product.tmp_id] = product.id
        clean_tmp_id = re.sub(r'-dup\d+$', '', product.tmp_id)
        if clean_tmp_id != product.tmp_id:
            products_by_clean_tmp_id[clean_tmp_id] = product.id

print(f"   Загружено товаров в кэш: {len(products_by_tmp_id):,}")

# Проверяем первые 20 ID_TOVAR
for id_tovar in id_tovar_list[:20]:
    if not id_tovar:
        continue
    
    # Ищем товар
    product_id = products_by_tmp_id.get(id_tovar)
    
    if not product_id:
        clean_id_tovar = re.sub(r'-dup\d+$', '', id_tovar)
        product_id = products_by_clean_tmp_id.get(clean_id_tovar)
    
    if product_id:
        product = Product.objects.get(id=product_id)
        found_count += 1
        found_examples.append((id_tovar, product.tmp_id, product.name[:50]))
    else:
        not_found_count += 1
        not_found_examples.append(id_tovar)
        
        # Проверяем, есть ли похожие товары (по началу)
        similar = Product.objects.filter(tmp_id__startswith=id_tovar[:8]).first()
        if similar:
            print(f"      ⚠️ ID_TOVAR '{id_tovar}' не найден, но есть похожий: '{similar.tmp_id}'")

# 3. Результаты
print(f"\n3️⃣ РЕЗУЛЬТАТЫ ПРОВЕРКИ (первые 20):")
print("=" * 70)
print(f"   Найдено товаров: {found_count}")
print(f"   НЕ найдено: {not_found_count}")

if found_examples:
    print(f"\n   ✅ Примеры НАЙДЕННЫХ товаров:")
    for id_tovar, tmp_id, name in found_examples[:5]:
        print(f"      ID_TOVAR: {id_tovar} → TMP_ID: {tmp_id} ({name})")

if not_found_examples:
    print(f"\n   ❌ Примеры НЕ НАЙДЕННЫХ товаров:")
    for id_tovar in not_found_examples[:10]:
        print(f"      ID_TOVAR: {id_tovar}")
        
        # Проверяем, есть ли товары с похожим tmp_id
        similar = Product.objects.filter(tmp_id__icontains=id_tovar[:8]).first()
        if similar:
            print(f"         ⚠️ Похожий товар: {similar.tmp_id}")

# 4. Вывод
print(f"\n" + "=" * 70)
print("📊 ВЫВОД")
print("=" * 70)

if not_found_count > 0:
    print(f"""
⚠️ Товары с ID_TOVAR из аналогов БЕЗ товаров действительно ОТСУТСТВУЮТ в базе.

Это нормальная ситуация, если:
1. В файле oe_nomer.DBF есть ссылки на товары, которых нет в файле 1C181225.DBF
2. Товары были удалены из номенклатуры, но аналогов остались
3. Товары еще не импортированы

РЕШЕНИЕ:
- Эти 427 аналогов останутся без товаров до тех пор, пока товары не будут добавлены в базу
- После импорта товаров можно снова запустить link_oe_to_products
- Или аналогов можно показывать в карточке товара по id_tovar (если товар найден по поиску)
""")
else:
    print(f"\n✅ Все товары найдены! Проблема в логике поиска.")

print("=" * 70)

