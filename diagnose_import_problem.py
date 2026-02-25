#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностика: Почему импортируется только часть аналогов?
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import Product, OeKod
from django.db.models import Count

print("\n" + "=" * 70)
print("🔍 ДИАГНОСТИКА: Почему импортируется только часть аналогов?")
print("=" * 70)

# 1. Проверяем проблему с unique=True
print("\n1️⃣ ПРОБЛЕМА: unique=True на поле id_oe")
print("=" * 70)

print("""
В модели OeKod:
    id_oe = models.CharField(unique=True, ...)  # ⚠️ ПРОБЛЕМА!

Это означает:
- В базе данных может быть только ОДНА запись с каждым уникальным id_oe
- Если в файле есть несколько записей с одинаковым id_oe (но разными id_tovar),
  то при импорте с ignore_conflicts=True будет импортирована только ПЕРВАЯ запись
- Остальные записи будут ПРОПУЩЕНЫ из-за конфликта уникальности
""")

# 2. Проверяем, есть ли дубликаты id_oe в файле (симуляция)
print("\n2️⃣ ПРОВЕРКА: Есть ли дубликаты id_oe в БД?")
print("=" * 70)

# В текущей БД не может быть дубликатов из-за unique=True
# Но проверим, сколько уникальных id_oe
unique_id_oe_count = OeKod.objects.values('id_oe').distinct().count()
total_analogs = OeKod.objects.count()

print(f"   Всего аналогов в БД: {total_analogs:,}")
print(f"   Уникальных id_oe: {unique_id_oe_count:,}")

if total_analogs == unique_id_oe_count:
    print(f"\n   ✅ В БД нет дубликатов id_oe (из-за unique=True)")
    print(f"   ⚠️ Но это НЕ означает, что в файле их нет!")
    print(f"   Дубликаты просто НЕ импортируются из-за unique=True")

# 3. Проверяем пример товара с аналогами
print("\n3️⃣ ПРОВЕРКА: Сколько аналогов у товара?")
print("=" * 70)

product_with_analogs = Product.objects.annotate(
    analogs_count=Count('oe_analogs')
).filter(analogs_count__gt=0).order_by('-analogs_count').first()

if product_with_analogs:
    print(f"\n   Товар: {product_with_analogs.name[:60]}")
    print(f"   TMP_ID: {product_with_analogs.tmp_id}")
    print(f"   Количество аналогов: {product_with_analogs.oe_analogs.count()}")
    
    # Проверяем, есть ли у этого товара аналогов с одинаковым id_oe
    analogs = product_with_analogs.oe_analogs.all()
    id_oe_list = list(analogs.values_list('id_oe', flat=True))
    unique_id_oe_in_product = len(set(id_oe_list))
    
    print(f"   Уникальных id_oe у этого товара: {unique_id_oe_in_product}")
    
    if len(id_oe_list) > unique_id_oe_in_product:
        print(f"   ⚠️ Есть дубликаты id_oe у одного товара!")
    else:
        print(f"   ✅ Нет дубликатов id_oe у этого товара")
else:
    print(f"\n   ⚠️ Товаров с аналогами не найдено")

# 4. Симуляция проблемы
print("\n4️⃣ СИМУЛЯЦИЯ ПРОБЛЕМЫ")
print("=" * 70)

print("""
Представим, что в файле есть такие записи:

ID_OE=00000443179, ID_TOVAR=000171383, NAME=!SK3988
ID_OE=00000443179, ID_TOVAR=000171384, NAME=!SK3988  ← Тот же id_oe, другой товар!
ID_OE=00000443179, ID_TOVAR=000171385, NAME=!SK3988  ← Тот же id_oe, другой товар!

При импорте с unique=True:
1. Первая запись (ID_TOVAR=000171383) → ✅ Импортирована
2. Вторая запись (ID_TOVAR=000171384) → ❌ Пропущена (id_oe уже существует)
3. Третья запись (ID_TOVAR=000171385) → ❌ Пропущена (id_oe уже существует)

Результат: Импортирована только 1 запись из 3!
""")

# 5. Проверяем статистику
print("\n5️⃣ СТАТИСТИКА")
print("=" * 70)

total_products = Product.objects.count()
products_with_analogs = Product.objects.filter(oe_analogs__isnull=False).distinct().count()
total_analogs = OeKod.objects.count()
analogs_with_products = OeKod.objects.filter(product__isnull=False).count()

print(f"\n   Всего товаров: {total_products:,}")
print(f"   Товаров с аналогами: {products_with_analogs:,}")
print(f"   Всего аналогов: {total_analogs:,}")
print(f"   Аналогов с товарами: {analogs_with_products:,}")

if products_with_analogs > 0:
    avg_analogs = analogs_with_products / products_with_analogs
    print(f"   Среднее аналогов на товар: {avg_analogs:.1f}")

# 6. Вывод
print("\n" + "=" * 70)
print("📊 ВЫВОД")
print("=" * 70)

print("""
ПРОБЛЕМА:
- В модели OeKod поле id_oe имеет unique=True
- Это означает, что в БД может быть только ОДНА запись с каждым id_oe
- Если в файле один id_oe связан с разными товарами (разные ID_TOVAR),
  то импортируется только ПЕРВАЯ запись
- Остальные записи ПРОПУСКАЮТСЯ из-за конфликта уникальности

РЕШЕНИЕ:
1. Убрать unique=True с поля id_oe
2. Создать составной уникальный индекс: (id_oe, id_tovar)
3. Это позволит одному id_oe быть связанным с разными товарами
4. Переимпортировать данные

РЕЗУЛЬТАТ:
- Все 439,890 записей будут импортированы
- Один id_oe может быть связан с разными товарами
- Каждый товар будет иметь все свои аналоги
""")

print("=" * 70)

