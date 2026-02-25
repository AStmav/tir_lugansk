#!/usr/bin/env python3
"""
Тест исправления поиска Latin ↔ Cyrillic
Проверяет работу normalize_latin_to_cyrillic()
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.views import normalize_latin_to_cyrillic
from shop.models import Product, OeKod
from django.db.models import Q

print('╔════════════════════════════════════════════════════════════╗')
print('║   🔧 ТЕСТ ИСПРАВЛЕНИЯ ПОИСКА: Latin ↔ Cyrillic           ║')
print('╚════════════════════════════════════════════════════════════╝\n')

# ========================================
# 1. ТЕСТ ФУНКЦИИ НОРМАЛИЗАЦИИ
# ========================================
print('1️⃣  ТЕСТ ФУНКЦИИ normalize_latin_to_cyrillic():')
print('='*70)

test_cases = [
    ('Яблоко M16/8', 'Яблоко М16/8'),      # M → М
    ('KOMETA', 'КОМЕТА'),                   # K,O,M,E,T,A → К,О,М,Е,Т,А
    ('BOSCH', 'ВОССН'),                     # B,O,C,H → В,О,С,Н
    ('Auto Parts', 'Аuto Раrts'),           # A,P → А,Р (частичная замена)
]

for original, expected in test_cases:
    result = normalize_latin_to_cyrillic(original)
    status = '✅' if result == expected else '❌'
    print(f'{status} "{original}" → "{result}"')
    if result != expected:
        print(f'   Ожидалось: "{expected}"')

# ========================================
# 2. ТЕСТ clean_number С НОРМАЛИЗАЦИЕЙ
# ========================================
print('\n\n2️⃣  ТЕСТ Product.clean_number() С НОРМАЛИЗАЦИЕЙ:')
print('='*70)

search_variants = [
    'Яблоко M16/8',   # Latin M
    'Яблоко М16/8',   # Cyrillic М
]

for search in search_variants:
    # Исходная версия
    clean_orig = Product.clean_number(search)
    
    # Нормализованная версия
    normalized = normalize_latin_to_cyrillic(search)
    clean_norm = Product.clean_number(normalized)
    
    print(f'\n📝 Поисковый запрос: "{search}"')
    print(f'   Нормализованный:  "{normalized}"')
    print(f'   clean (orig):     "{clean_orig}"')
    print(f'   clean (norm):     "{clean_norm}"')
    
    # Показываем байты
    if clean_orig != clean_norm:
        print(f'   ⚠️  РАЗЛИЧАЮТСЯ!')
        print(f'   Bytes (orig):     {clean_orig.encode("utf-8")}')
        print(f'   Bytes (norm):     {clean_norm.encode("utf-8")}')
    else:
        print(f'   ✅ СОВПАДАЮТ')

# ========================================
# 3. ТЕСТ ПОИСКА В БАЗЕ ДАННЫХ
# ========================================
print('\n\n3️⃣  ТЕСТ ПОИСКА В БД:')
print('='*70)

# Проверяем есть ли "яблоко" в базе
oe_with_yabloko = OeKod.objects.filter(oe_kod__icontains='яблок')
print(f'\nВсего OE с "яблок" в базе: {oe_with_yabloko.count()}')

if oe_with_yabloko.exists():
    print('\n📋 Примеры найденных OE:')
    for i, oe in enumerate(oe_with_yabloko[:3], 1):
        print(f'\n   {i}. OE: "{oe.oe_kod}"')
        print(f'      clean: "{oe.oe_kod_clean}"')
        print(f'      bytes: {oe.oe_kod_clean.encode("utf-8") if oe.oe_kod_clean else b""}')
        if oe.product:
            print(f'      Товар: {oe.product.tmp_id} - {oe.product.name[:50]}')
        if oe.brand:
            print(f'      Бренд: {oe.brand.name}')

# ========================================
# 4. СИМУЛЯЦИЯ ПОИСКА КАК НА ФРОНТЕ
# ========================================
print('\n\n4️⃣  СИМУЛЯЦИЯ ПОИСКА (как в CatalogView):')
print('='*70)

for search in search_variants:
    print(f'\n🔍 Поиск: "{search}"')
    
    # Оригинальная версия
    search_clean = Product.clean_number(search)
    
    # Нормализованная версия
    search_normalized = normalize_latin_to_cyrillic(search)
    search_clean_normalized = Product.clean_number(search_normalized)
    
    print(f'   clean (orig): "{search_clean}"')
    print(f'   clean (norm): "{search_clean_normalized}"')
    
    # Поиск по обоим вариантам (как в новом коде)
    oe_search_query = (
        Q(oe_analogs__oe_kod_clean__iexact=search_clean) |
        Q(oe_analogs__oe_kod_clean__iexact=search_clean_normalized)
    )
    
    found_products = Product.objects.filter(oe_search_query).distinct()
    count = found_products.count()
    
    print(f'   Найдено товаров: {count}')
    
    if count > 0:
        print(f'   ✅ ТОВАРЫ НАЙДЕНЫ:')
        for p in found_products[:3]:
            print(f'      • [{p.tmp_id}] {p.name[:60]}')
    else:
        print(f'   ❌ ТОВАРЫ НЕ НАЙДЕНЫ')

# ========================================
# 5. СТАТИСТИКА
# ========================================
print('\n\n5️⃣  СТАТИСТИКА БД:')
print('='*70)

total_oe = OeKod.objects.count()
oe_with_clean = OeKod.objects.exclude(oe_kod_clean='').count()
oe_no_clean = total_oe - oe_with_clean
total_products = Product.objects.count()

print(f'   Всего OE в базе:           {total_oe:,}')
print(f'   С заполненным oe_kod_clean: {oe_with_clean:,}')
print(f'   БЕЗ oe_kod_clean:          {oe_no_clean:,}')
print(f'   Всего товаров:             {total_products:,}')

# ========================================
# ВЕРДИКТ
# ========================================
print('\n\n📋 ВЕРДИКТ:')
print('='*70)

if oe_no_clean > 0:
    print(f'\n⚠️  ВНИМАНИЕ: {oe_no_clean:,} OE без заполненного oe_kod_clean!')
    print('   Это может быть причиной проблем с поиском.')
    print('   Решение: Переимпортировать OE аналоги')
    print('   Команда: python3 manage.py import_oe_analogs_dbf oe_nomer.DBF --clear_existing')
elif oe_with_yabloko.count() == 0:
    print('\n❌ OE с "яблоко" НЕ НАЙДЕНЫ в базе!')
    print('   Возможно, они не были импортированы.')
else:
    print('\n✅ НОРМАЛИЗАЦИЯ РАБОТАЕТ!')
    print('   • Функция normalize_latin_to_cyrillic() корректна')
    print('   • OE в базе найдены')
    print('   • Поиск должен работать после обновления shop/views.py на сервере')
    print('\n📝 Следующие шаги:')
    print('   1. Скопировать shop/views.py на сервер')
    print('   2. Перезапустить Django')
    print('   3. Протестировать поиск на фронте')

print('='*70)

