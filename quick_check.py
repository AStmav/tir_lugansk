#!/usr/bin/env python3
"""
Простейший скрипт проверки БД
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')

import django
django.setup()

from shop.models import Product

print("\n" + "=" * 70)
print("📊 ПРОВЕРКА БАЗЫ ДАННЫХ")
print("=" * 70)

total = Product.objects.count()
with_dup = Product.objects.filter(tmp_id__icontains='-dup').count()
without_dup = total - with_dup

print(f"\nВсего товаров:      {total:,}")
print(f"С -dup:             {with_dup:,} ({with_dup/total*100:.1f}%)")
print(f"Без -dup:           {without_dup:,} ({without_dup/total*100:.1f}%)")
print(f"Ожидается:          198,538")
print("\n" + "=" * 70)

if with_dup > 0:
    print(f"\n⚠️  НАЙДЕНО {with_dup:,} ДУБЛИКАТОВ!")
    print(f"\nДля удаления запустите:")
    print(f"python3 check_and_remove_duplicates.py")
else:
    print("\n✅ Дубликатов нет! База чистая.")

print()

