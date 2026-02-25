#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка: Количество уникальных ID_OE
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import OeKod, Product
from django.db.models import Count

print("\n" + "=" * 70)
print("🔍 ПРОВЕРКА: Количество уникальных ID_OE")
print("=" * 70)

# 1. Общее количество аналогов
total = OeKod.objects.count()
print(f"\n1️⃣ Всего аналогов в БД: {total:,}")

# 2. Количество уникальных ID_OE
unique_id_oe = OeKod.objects.values('id_oe').distinct().count()
print(f"2️⃣ Уникальных ID_OE: {unique_id_oe:,}")

# 3. Сравнение
if total == unique_id_oe:
    print(f"\n✅ ВСЁ ПРАВИЛЬНО!")
    print(f"   Все аналогов имеют уникальные ID_OE")
    print(f"   Дубликатов нет")
else:
    print(f"\n⚠️ ОБНАРУЖЕНА ПРОБЛЕМА!")
    print(f"   Всего аналогов: {total:,}")
    print(f"   Уникальных ID_OE: {unique_id_oe:,}")
    print(f"   Разница: {total - unique_id_oe:,}")
    print(f"   Это означает, что есть дубликаты ID_OE")

# 4. Проверка товара с аналогами
print(f"\n3️⃣ ПРОВЕРКА: Товар с аналогами")
print("=" * 70)

product = Product.objects.annotate(
    analogs_count=Count('oe_analogs')
).filter(analogs_count__gt=0).order_by('-analogs_count').first()

if product:
    print(f"\n   Товар: {product.name[:60]}")
    print(f"   TMP_ID: {product.tmp_id}")
    print(f"   Количество аналогов: {product.oe_analogs.count()}")
    
    # Проверяем уникальность ID_OE у этого товара
    id_oe_list = list(product.oe_analogs.values_list('id_oe', flat=True))
    unique_id_oe_in_product = len(set(id_oe_list))
    
    print(f"   Уникальных ID_OE у товара: {unique_id_oe_in_product}")
    print(f"   Всего записей: {len(id_oe_list)}")
    
    if len(id_oe_list) == unique_id_oe_in_product:
        print(f"   ✅ Все ID_OE уникальны у этого товара")
    else:
        print(f"   ⚠️ Есть дубликаты ID_OE у этого товара!")
        print(f"   Это НЕ должно быть, если ID_OE уникальный!")
else:
    print(f"\n   ⚠️ Товаров с аналогами не найдено")

# 5. Проверка на дубликаты ID_OE
print(f"\n4️⃣ ПРОВЕРКА: Дубликаты ID_OE")
print("=" * 70)

from django.db.models import Count

duplicates = OeKod.objects.values('id_oe').annotate(
    count=Count('id_oe')
).filter(count__gt=1)

if duplicates.exists():
    print(f"\n   ⚠️ Найдено дубликатов ID_OE: {duplicates.count()}")
    print(f"   Примеры дубликатов:")
    for dup in duplicates[:5]:
        print(f"      ID_OE={dup['id_oe']}: {dup['count']} записей")
        # Показываем примеры
        examples = OeKod.objects.filter(id_oe=dup['id_oe'])[:3]
        for ex in examples:
            print(f"         - ID_TOVAR: {ex.id_tovar}, OE: {ex.oe_kod}")
else:
    print(f"\n   ✅ Дубликатов ID_OE не найдено")
    print(f"   Все ID_OE уникальны")

# 6. Итог
print(f"\n" + "=" * 70)
print("📊 ИТОГО")
print("=" * 70)

if total == unique_id_oe and not duplicates.exists():
    print(f"""
✅ ВСЁ ПРАВИЛЬНО!
   - Всего аналогов: {total:,}
   - Уникальных ID_OE: {unique_id_oe:,}
   - Дубликатов нет
   - Логика связей правильная: один товар → много аналогов
""")
else:
    print(f"""
⚠️ ОБНАРУЖЕНА ПРОБЛЕМА!
   - Всего аналогов: {total:,}
   - Уникальных ID_OE: {unique_id_oe:,}
   - Дубликатов: {duplicates.count() if duplicates.exists() else 0}
   
   Если ID_OE должен быть уникальным, но есть дубликаты,
   это означает проблему в данных или логике импорта.
""")

print("=" * 70)

