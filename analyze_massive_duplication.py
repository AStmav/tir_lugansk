#!/usr/bin/env python3
"""
🚨 КРИТИЧЕСКИЙ АНАЛИЗ: Массовая дупликация товаров
Проверяем масштаб проблемы и причины
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import Product, Brand, OeKod, ProductImage

print('╔════════════════════════════════════════════════════════════════════╗')
print('║   🚨 КРИТИЧЕСКИЙ АНАЛИЗ: Дупликация товаров                       ║')
print('╚════════════════════════════════════════════════════════════════════╝\n')

# ========================================
# 1. ОБЩАЯ СТАТИСТИКА
# ========================================
print('='*80)
print('1️⃣  ОБЩАЯ СТАТИСТИКА:')
print('='*80)

total_products = Product.objects.count()
print(f'\n📊 Всего товаров в базе: {total_products:,}')
print(f'📄 Ожидалось (из файла):  198,538')
print(f'🔴 РАЗНИЦА:               {total_products - 198538:,} товаров')
print(f'📈 КОЭФФИЦИЕНТ:           {total_products / 198538:.2f}x\n')

# ========================================
# 2. АНАЛИЗ ДУБЛИКАТОВ -dup
# ========================================
print('='*80)
print('2️⃣  АНАЛИЗ ТОВАРОВ С СУФФИКСОМ -dup:')
print('='*80)

products_with_dup = Product.objects.filter(tmp_id__icontains='-dup').count()
products_without_dup = Product.objects.exclude(tmp_id__icontains='-dup').count()

print(f'\n🔴 С суффиксом -dup:  {products_with_dup:,} товаров')
print(f'✅ Без суффикса -dup: {products_without_dup:,} товаров')
print(f'📊 Процент дубликатов: {(products_with_dup / total_products * 100):.1f}%\n')

# Анализ по типам дубликатов
dup1_count = Product.objects.filter(tmp_id__icontains='-dup1').count()
dup2_count = Product.objects.filter(tmp_id__icontains='-dup2').count()
dup3_count = Product.objects.filter(tmp_id__icontains='-dup3').count()
dup4_count = Product.objects.filter(tmp_id__icontains='-dup4').count()
dup5plus = products_with_dup - (dup1_count + dup2_count + dup3_count + dup4_count)

print('📋 Распределение по типам:')
print(f'   -dup1:  {dup1_count:,}')
print(f'   -dup2:  {dup2_count:,}')
print(f'   -dup3:  {dup3_count:,}')
print(f'   -dup4:  {dup4_count:,}')
if dup5plus > 0:
    print(f'   -dup5+: {dup5plus:,}')

# ========================================
# 3. ПРОВЕРКА НА ДВОЙНОЙ ИМПОРТ
# ========================================
print('\n' + '='*80)
print('3️⃣  ПРОВЕРКА НА ДВОЙНОЙ ИМПОРТ:')
print('='*80)

# Если products_without_dup близко к 198538, значит был двойной импорт
expected = 198538
if abs(products_without_dup - expected) < 1000:
    print(f'\n⚠️  ВЕРОЯТНАЯ ПРИЧИНА: Импорт запускался ДВАЖДЫ!')
    print(f'   • Товаров без -dup: {products_without_dup:,}')
    print(f'   • Ожидалось:        {expected:,}')
    print(f'   • Разница:          {abs(products_without_dup - expected):,}')
    print(f'\n   💡 При втором импорте для каждого дубликата добавлялся суффикс -dup')
elif products_with_dup > products_without_dup * 0.8:
    print(f'\n⚠️  МАССИВНАЯ ДУПЛИКАЦИЯ!')
    print(f'   • {(products_with_dup / total_products * 100):.0f}% товаров — дубликаты!')
else:
    print(f'\n✅ Дубликатов относительно немного')
    print(f'   • {(products_with_dup / total_products * 100):.1f}% от общего числа')

# ========================================
# 4. ПРИМЕРЫ ДУБЛИКАТОВ
# ========================================
print('\n' + '='*80)
print('4️⃣  ПРИМЕРЫ ДУБЛИКАТОВ:')
print('='*80)

# Найти оригиналы, у которых есть дубликаты
print('\n🔍 Ищем товары с дубликатами...')

# Берем несколько товаров с -dup1
sample_dups = Product.objects.filter(tmp_id__icontains='-dup1')[:5]

for dup in sample_dups:
    # Получаем базовый tmp_id
    base_tmp_id = dup.tmp_id.split('-dup')[0]
    
    # Ищем оригинал
    original = Product.objects.filter(tmp_id=base_tmp_id).first()
    
    # Ищем все дубликаты этого товара
    all_versions = Product.objects.filter(
        tmp_id__startswith=base_tmp_id
    ).order_by('tmp_id')
    
    print(f'\n📦 Товар: {dup.name[:50]}')
    print(f'   Базовый ID: {base_tmp_id}')
    print(f'   Всего версий: {all_versions.count()}')
    
    for v in all_versions:
        status = '✅ ОРИГИНАЛ' if v.tmp_id == base_tmp_id else '🔴 ДУБЛИКАТ'
        print(f'      {status} [{v.tmp_id}]')
        print(f'         Название: {v.name[:40]}')
        print(f'         Бренд: {v.brand.name if v.brand else "НЕТ"}')
        print(f'         Каталожный: {v.catalog_number}')

# ========================================
# 5. СВЯЗАННЫЕ ДАННЫЕ
# ========================================
print('\n' + '='*80)
print('5️⃣  СВЯЗАННЫЕ ДАННЫЕ (OE, изображения):')
print('='*80)

total_oe = OeKod.objects.count()
oe_with_dup = OeKod.objects.filter(product__tmp_id__icontains='-dup').count()

total_images = ProductImage.objects.count()
images_with_dup = ProductImage.objects.filter(product__tmp_id__icontains='-dup').count()

print(f'\n🔗 OE аналоги:')
print(f'   Всего:          {total_oe:,}')
print(f'   Для -dup:       {oe_with_dup:,} ({(oe_with_dup/total_oe*100):.1f}%)')
print(f'   Для оригиналов: {total_oe - oe_with_dup:,}')

print(f'\n🖼️  Изображения:')
print(f'   Всего:          {total_images:,}')
print(f'   Для -dup:       {images_with_dup:,} ({(images_with_dup/total_images*100 if total_images > 0 else 0):.1f}%)')
print(f'   Для оригиналов: {total_images - images_with_dup:,}')

# ========================================
# 6. РЕКОМЕНДАЦИИ
# ========================================
print('\n' + '='*80)
print('📋 РЕКОМЕНДАЦИИ:')
print('='*80)

if products_with_dup > total_products * 0.4:
    print(f'\n🚨 КРИТИЧЕСКАЯ ПРОБЛЕМА!')
    print(f'   {products_with_dup:,} товаров ({(products_with_dup/total_products*100):.0f}%) — дубликаты!\n')
    
    print('💡 РЕШЕНИЕ 1: Удалить все товары с -dup')
    print('   Команда:')
    print('   ```python')
    print('   Product.objects.filter(tmp_id__icontains=\"-dup\").delete()')
    print('   ```')
    print(f'   Результат: {products_without_dup:,} товаров (близко к 198,538)')
    
    print('\n💡 РЕШЕНИЕ 2: Полный переимпорт')
    print('   1. Удалить ВСЕ товары')
    print('   2. Переимпортировать с флагом --clear_existing')
    print('   3. Проверить результат')
    
    print('\n💡 РЕШЕНИЕ 3: Скрыть -dup в поиске (временное)')
    print('   Добавить фильтр в shop/views.py:')
    print('   queryset = queryset.exclude(tmp_id__icontains=\"-dup\")')
    
else:
    print(f'\n✅ Проблема локальная')
    print(f'   Только {products_with_dup:,} дубликатов')
    print(f'   Можно просто скрыть их в поиске')

# ========================================
# 7. ПРОВЕРКА ИМПОРТА
# ========================================
print('\n' + '='*80)
print('7️⃣  ИСТОРИЯ ИМПОРТА:')
print('='*80)

from shop.models import ImportFile

imports = ImportFile.objects.filter(file_type='products').order_by('-uploaded_at')[:5]

if imports.exists():
    print(f'\n📁 Последние импорты товаров:')
    for imp in imports:
        print(f'\n   Файл: {imp.original_filename}')
        print(f'   Дата: {imp.uploaded_at}')
        print(f'   Статус: {imp.status}')
        print(f'   Создано: {imp.created_rows:,}')
        print(f'   Обновлено: {imp.updated_rows:,}')
else:
    print('\n❌ История импорта недоступна')

print('\n' + '='*80)
print('✅ АНАЛИЗ ЗАВЕРШЕН')
print('='*80)

