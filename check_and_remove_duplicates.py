#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой скрипт для проверки и удаления дубликатов
"""

import os
import sys

# Проверяем что мы в правильной директории
if not os.path.exists('db.sqlite3'):
    print("❌ ОШИБКА: Файл db.sqlite3 не найден!")
    print(f"   Текущая директория: {os.getcwd()}")
    sys.exit(1)

print("✅ Файл db.sqlite3 найден")
print(f"   Размер: {os.path.getsize('db.sqlite3') / (1024*1024):.1f} MB")
print("")

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')

try:
    import django
    django.setup()
    print("✅ Django настроен")
except Exception as e:
    print(f"❌ Ошибка настройки Django: {e}")
    sys.exit(1)

from shop.models import Product, OeKod, ProductImage

print("")
print("=" * 70)
print("📊 ТЕКУЩЕЕ СОСТОЯНИЕ БАЗЫ ДАННЫХ")
print("=" * 70)

total = Product.objects.count()
with_dup = Product.objects.filter(tmp_id__icontains='-dup').count()
without_dup = total - with_dup

print(f"Всего товаров:      {total:,}")
print(f"С суффиксом -dup:   {with_dup:,} ({with_dup/total*100:.1f}% от общего)")
print(f"Без суффикса -dup:  {without_dup:,} ({without_dup/total*100:.1f}% от общего)")
print(f"Ожидается товаров:  198,538")
print("=" * 70)

if with_dup == 0:
    print("")
    print("✅ Дубликатов не обнаружено! База данных чистая.")
    sys.exit(0)

print("")
print(f"⚠️  Обнаружено {with_dup:,} товаров с суффиксом '-dup'")
print("")

# Проверяем связанные объекты
oe_count = OeKod.objects.filter(product__tmp_id__icontains='-dup').count()
img_count = ProductImage.objects.filter(product__tmp_id__icontains='-dup').count()

if oe_count > 0:
    print(f"   - {oe_count:,} OE аналогов связаны с дубликатами")
if img_count > 0:
    print(f"   - {img_count:,} изображений связаны с дубликатами")

print("")
print("⚠️  Эти объекты будут удалены КАСКАДНО вместе с дубликатами!")
print("")

# Запрашиваем подтверждение
response = input(f"Удалить {with_dup:,} дубликатов и связанные объекты? (yes/no): ")

if response.lower() != 'yes':
    print("")
    print("❌ Удаление отменено")
    sys.exit(0)

print("")
print("🗑️  УДАЛЕНИЕ...")
print("=" * 70)

from django.db import transaction

with transaction.atomic():
    duplicate_products = Product.objects.filter(tmp_id__icontains='-dup')
    deleted_count, details = duplicate_products.delete()
    
    print(f"✅ Удалено записей: {deleted_count:,}")
    print("")
    print("Детали удаления:")
    for model, count in details.items():
        if count > 0:
            print(f"   - {model}: {count:,}")

print("")
print("=" * 70)
print("📊 ФИНАЛЬНОЕ СОСТОЯНИЕ")
print("=" * 70)

final_total = Product.objects.count()
final_with_dup = Product.objects.filter(tmp_id__icontains='-dup').count()

print(f"Всего товаров:      {final_total:,}")
print(f"С суффиксом -dup:   {final_with_dup}")
print(f"Ожидалось:          198,538")
print(f"Разница:            {abs(final_total - 198538):,}")

print("")
if final_with_dup == 0:
    print("✅✅✅ ОТЛИЧНО! ДУБЛИКАТЫ УСПЕШНО УДАЛЕНЫ! ✅✅✅")
else:
    print(f"⚠️  Осталось {final_with_dup} дубликатов")

print("")
print("=" * 70)
print("🎉 ГОТОВО!")
print("=" * 70)

