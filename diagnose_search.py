#!/usr/bin/env python3
"""
Диагностика поиска "Яблоко M16/8"
Проверяем:
1. Есть ли OE с таким номером в БД
2. Какая версия записана (латиница/кириллица)
3. Как работает clean_number для разных вариантов
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import OeKod, Product

print('╔════════════════════════════════════════════════════════════╗')
print('║       🔍 ДИАГНОСТИКА ПОИСКА: Яблоко M16/8                 ║')
print('╚════════════════════════════════════════════════════════════╝\n')

# Варианты написания (латиница M vs кириллица М)
variants = [
    ('Яблоко M16/8', 'Латинская M'),
    ('Яблоко М16/8', 'Кириллическая М'),
    ('яблоко m16/8', 'Латинская m (lowercase)'),
    ('яблоко м16/8', 'Кириллическая м (lowercase)'),
]

print('1️⃣  ТЕСТИРОВАНИЕ ФУНКЦИИ clean_number():')
print('='*70)
for variant, desc in variants:
    cleaned = Product.clean_number(variant)
    print(f'   "{variant}" ({desc})')
    print(f'   → cleaned: "{cleaned}"')
    print(f'   → bytes: {cleaned.encode("utf-8")}')
    print()

# Проверяем что есть в БД
print('\n2️⃣  ПОИСК В БАЗЕ ДАННЫХ:')
print('='*70)

# Ищем все OE содержащие "яблоко" (регистронезависимо)
oe_results = OeKod.objects.filter(oe_kod__icontains='яблок').order_by('oe_kod')
print(f'   Найдено OE с "яблок": {oe_results.count()}\n')

if oe_results.exists():
    print('   📋 Список найденных OE:')
    for i, oe in enumerate(oe_results[:10], 1):
        product_info = f'{oe.product.tmp_id} - {oe.product.name[:40]}' if oe.product else 'НЕТ ТОВАРА'
        brand_info = oe.brand.name if oe.brand else 'НЕТ БРЕНДА'
        
        print(f'\n   {i}. OE: "{oe.oe_kod}"')
        print(f'      clean: "{oe.oe_kod_clean}"')
        print(f'      bytes: {oe.oe_kod_clean.encode("utf-8") if oe.oe_kod_clean else b""}')
        print(f'      Бренд: {brand_info}')
        print(f'      Товар: {product_info}')

# Пробуем точный поиск по всем вариантам cleaned
print('\n\n3️⃣  ТОЧНЫЙ ПОИСК ПО CLEANED ВЕРСИЯМ:')
print('='*70)

for variant, desc in variants:
    cleaned = Product.clean_number(variant)
    results = OeKod.objects.filter(oe_kod_clean__iexact=cleaned)
    count = results.count()
    
    print(f'\n   Поиск: "{cleaned}" ({desc})')
    print(f'   Найдено: {count}')
    
    if count > 0:
        oe = results.first()
        print(f'   ✅ НАЙДЕН: "{oe.oe_kod}" → товар {oe.product.tmp_id if oe.product else "N/A"}')

# Статистика
print('\n\n4️⃣  СТАТИСТИКА:')
print('='*70)
total_oe = OeKod.objects.count()
oe_with_clean = OeKod.objects.exclude(oe_kod_clean='').count()
oe_no_clean = OeKod.objects.filter(oe_kod_clean='').count()

print(f'   Всего OE в базе: {total_oe:,}')
print(f'   С заполненным oe_kod_clean: {oe_with_clean:,}')
print(f'   БЕЗ oe_kod_clean: {oe_no_clean:,}')

# ВЕРДИКТ
print('\n\n📋 ВЕРДИКТ:')
print('='*70)
if oe_no_clean > 0:
    print(f'\n⚠️  ПРОБЛЕМА: {oe_no_clean:,} OE без заполненного oe_kod_clean!')
    print('   Решение: Нужно переимпортировать OE с обновленной логикой clean_number')
    print('   Команда: python3 manage.py import_oe_analogs_dbf oe_nomer.DBF --clear_existing')
elif oe_results.count() == 0:
    print('\n❌ ПРОБЛЕМА: OE "Яблоко" вообще нет в базе!')
    print('   Решение: Импортировать OE аналоги')
else:
    print('\n✅ OE с "яблоко" найдены!')
    print('   Проверьте соответствие Latin M vs Cyrillic М в логах выше')

print('='*70)

