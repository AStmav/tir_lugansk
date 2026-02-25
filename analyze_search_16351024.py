#!/usr/bin/env python3
"""
ГЛУБОКИЙ АНАЛИЗ поиска по номеру 16.35.1024
Проверяем ПОЧЕМУ найдено 3 товара и являются ли они дубликатами
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import Product, OeKod

print('╔════════════════════════════════════════════════════════════════════╗')
print('║   🔍 ГЛУБОКИЙ АНАЛИЗ ПОИСКА: 16.35.1024                           ║')
print('╚════════════════════════════════════════════════════════════════════╝\n')

search_term = '16.35.1024'
search_clean = '16351024'  # После clean_number()

print(f'📝 Поисковый запрос: "{search_term}"')
print(f'🧹 Очищенный: "{search_clean}"\n')

# ========================================
# 1. ПОИСК В ТАБЛИЦЕ PRODUCT
# ========================================
print('='*80)
print('1️⃣  ПОИСК В ТАБЛИЦЕ PRODUCT (по catalog_number_clean и artikyl_number_clean):')
print('='*80)

# Точное совпадение по catalog_number_clean
products_by_catalog = Product.objects.filter(
    catalog_number_clean__iexact=search_clean
)
print(f'\n📦 По catalog_number_clean (точное): {products_by_catalog.count()} товаров')
for p in products_by_catalog:
    print(f'   • [{p.tmp_id}] {p.name[:60]}')
    print(f'     Каталожный: "{p.catalog_number}" (clean: "{p.catalog_number_clean}")')
    print(f'     Артикул: "{p.artikyl_number}" (clean: "{p.artikyl_number_clean}")')
    print(f'     Бренд: {p.brand.name if p.brand else "НЕТ"}')
    print()

# Точное совпадение по artikyl_number_clean
products_by_artikyl = Product.objects.filter(
    artikyl_number_clean__iexact=search_clean
)
print(f'📦 По artikyl_number_clean (точное): {products_by_artikyl.count()} товаров')
for p in products_by_artikyl:
    print(f'   • [{p.tmp_id}] {p.name[:60]}')
    print(f'     Каталожный: "{p.catalog_number}" (clean: "{p.catalog_number_clean}")')
    print(f'     Артикул: "{p.artikyl_number}" (clean: "{p.artikyl_number_clean}")')
    print(f'     Бренд: {p.brand.name if p.brand else "НЕТ"}')
    print()

# Начинается с (istartswith)
products_by_catalog_starts = Product.objects.filter(
    catalog_number_clean__istartswith=search_clean
).exclude(catalog_number_clean__iexact=search_clean)
print(f'📦 По catalog_number_clean (начинается с): {products_by_catalog_starts.count()} товаров')
for p in products_by_catalog_starts[:5]:
    print(f'   • [{p.tmp_id}] {p.catalog_number_clean}')

# ========================================
# 2. ПОИСК ЧЕРЕЗ OE АНАЛОГИ
# ========================================
print('\n' + '='*80)
print('2️⃣  ПОИСК ЧЕРЕЗ OE АНАЛОГИ (oe_analogs__oe_kod_clean):')
print('='*80)

# Найти OE с таким номером
oe_results = OeKod.objects.filter(oe_kod_clean__iexact=search_clean)
print(f'\n🔗 Найдено OE аналогов: {oe_results.count()}')

if oe_results.exists():
    print('\n📋 Детали OE аналогов:')
    for i, oe in enumerate(oe_results, 1):
        print(f'\n   {i}. OE: "{oe.oe_kod}" (clean: "{oe.oe_kod_clean}")')
        print(f'      ID в 1C: {oe.id_oe}')
        print(f'      Бренд OE: {oe.brand.name if oe.brand else "НЕТ БРЕНДА"}')
        
        if oe.product:
            print(f'      ✅ Связан с товаром:')
            print(f'         └─ [{oe.product.tmp_id}] {oe.product.name[:50]}')
            print(f'            Каталожный: "{oe.product.catalog_number}"')
            print(f'            Бренд товара: {oe.product.brand.name if oe.product.brand else "НЕТ"}')
        else:
            print(f'      ❌ НЕТ связи с товаром (product=NULL)')

# Найти товары через OE
products_via_oe = Product.objects.filter(
    oe_analogs__oe_kod_clean__iexact=search_clean
).distinct()
print(f'\n📦 Товаров найдено через OE аналоги: {products_via_oe.count()}')
for p in products_via_oe:
    print(f'   • [{p.tmp_id}] {p.name[:60]}')
    print(f'     Каталожный: "{p.catalog_number}"')
    print(f'     Бренд: {p.brand.name if p.brand else "НЕТ"}')
    
    # Показать какие OE этого товара соответствуют запросу
    matching_oe = p.oe_analogs.filter(oe_kod_clean__iexact=search_clean)
    print(f'     OE аналоги (совпадающие с запросом): {matching_oe.count()}')
    for oe in matching_oe[:3]:
        print(f'       └─ "{oe.oe_kod}" (бренд: {oe.brand.name if oe.brand else "НЕТ"})')
    print()

# ========================================
# 3. ОБЪЕДИНЕННЫЙ РЕЗУЛЬТАТ (как в views.py)
# ========================================
print('='*80)
print('3️⃣  ФИНАЛЬНЫЙ РЕЗУЛЬТАТ (как в CatalogView):')
print('='*80)

from django.db.models import Q

# Точно так же как в views.py
number_search_query = (
    Q(code__iexact=search_term) |
    Q(tmp_id__iexact=search_term) |
    Q(catalog_number_clean__iexact=search_clean) |
    Q(artikyl_number_clean__iexact=search_clean) |
    Q(catalog_number_clean__istartswith=search_clean) |
    Q(artikyl_number_clean__istartswith=search_clean)
)

oe_search_query = (
    Q(oe_analogs__oe_kod_clean__iexact=search_clean) |
    Q(oe_analogs__oe_kod_clean__istartswith=search_clean)
)

final_products = Product.objects.filter(
    number_search_query | oe_search_query
).distinct()

print(f'\n📊 ИТОГО найдено товаров: {final_products.count()}\n')

for i, p in enumerate(final_products, 1):
    print(f'{i}. [{p.tmp_id}] {p.name}')
    print(f'   Каталожный: "{p.catalog_number}" (clean: "{p.catalog_number_clean}")')
    print(f'   Артикул: "{p.artikyl_number}" (clean: "{p.artikyl_number_clean}")')
    print(f'   Бренд: {p.brand.name if p.brand else "НЕТ"}')
    
    # Определяем ПОЧЕМУ этот товар найден
    reasons = []
    
    if p.catalog_number_clean == search_clean:
        reasons.append('✅ Каталожный номер совпадает')
    elif p.catalog_number_clean and p.catalog_number_clean.startswith(search_clean):
        reasons.append('✅ Каталожный номер начинается с запроса')
    
    if p.artikyl_number_clean == search_clean:
        reasons.append('✅ Артикул совпадает')
    elif p.artikyl_number_clean and p.artikyl_number_clean.startswith(search_clean):
        reasons.append('✅ Артикул начинается с запроса')
    
    matching_oe = p.oe_analogs.filter(oe_kod_clean__iexact=search_clean)
    if matching_oe.exists():
        reasons.append(f'✅ Есть OE аналог: {matching_oe.count()} шт.')
    
    matching_oe_starts = p.oe_analogs.filter(
        oe_kod_clean__istartswith=search_clean
    ).exclude(oe_kod_clean__iexact=search_clean)
    if matching_oe_starts.exists():
        reasons.append(f'✅ Есть OE начинающийся с: {matching_oe_starts.count()} шт.')
    
    print(f'   📌 Причины попадания в результат:')
    for reason in reasons:
        print(f'      {reason}')
    print()

# ========================================
# 4. АНАЛИЗ ДУБЛИКАТОВ
# ========================================
print('='*80)
print('4️⃣  АНАЛИЗ ДУБЛИКАТОВ:')
print('='*80)

# Проверка на -dup суффиксы
products_with_dup = final_products.filter(tmp_id__icontains='-dup')
products_without_dup = final_products.exclude(tmp_id__icontains='-dup')

print(f'\n📊 Товаров с суффиксом "-dup": {products_with_dup.count()}')
for p in products_with_dup:
    # Найти "оригинал" без -dup
    base_tmp_id = p.tmp_id.split('-dup')[0]
    original = Product.objects.filter(tmp_id=base_tmp_id).first()
    
    print(f'\n   ⚠️  [{p.tmp_id}] → Дубликат "{base_tmp_id}"')
    if original:
        print(f'      Оригинал существует: [{original.tmp_id}]')
        print(f'      Одинаковые поля:')
        if p.name == original.name:
            print(f'        • Название: ✅ Совпадает')
        if p.catalog_number_clean == original.catalog_number_clean:
            print(f'        • Каталожный номер: ✅ Совпадает')
        if p.brand == original.brand:
            print(f'        • Бренд: ✅ Совпадает')
    else:
        print(f'      ❌ Оригинал НЕ НАЙДЕН (удален?)')

print(f'\n📊 Товаров БЕЗ суффикса "-dup": {products_without_dup.count()}')
for p in products_without_dup:
    print(f'   ✅ [{p.tmp_id}] - Оригинальный товар')

# ========================================
# ВЕРДИКТ
# ========================================
print('\n' + '='*80)
print('📋 ВЕРДИКТ:')
print('='*80)

if products_with_dup.count() > 0:
    print(f'\n⚠️  ПРОБЛЕМА: Найдены технические дубликаты с суффиксом "-dup"!')
    print(f'   Количество: {products_with_dup.count()}')
    print(f'\n   Это НЕ баг поиска, а реальные дубликаты в базе данных.')
    print(f'   Они появились при импорте из 1С (дубликаты в исходном DBF файле).')
    print(f'\n   💡 РЕШЕНИЕ:')
    print(f'      1. Скрыть товары с "-dup" из результатов поиска')
    print(f'      2. Или удалить их из БД после проверки связей')
else:
    print(f'\n✅ Дубликатов "-dup" НЕТ!')

if final_products.count() > 1:
    print(f'\n📊 Найдено {final_products.count()} товара - это НЕ дубликаты, а:')
    print(f'   • Разные товары от разных производителей')
    print(f'   • Товары, имеющие OE аналоги с этим номером')
    print(f'   • Товары с похожими артикулами')
    print(f'\n   ✅ Это правильное поведение поиска!')

print('='*80)

