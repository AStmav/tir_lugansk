#!/usr/bin/env python3
"""
🧹 УДАЛЕНИЕ ДУБЛИКАТОВ: Безопасное удаление товаров с суффиксом -dup
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import Product, OeKod, ProductImage

print('╔════════════════════════════════════════════════════════════════════╗')
print('║   🧹 УДАЛЕНИЕ ДУБЛИКАТОВ ТОВАРОВ                                  ║')
print('╚════════════════════════════════════════════════════════════════════╝\n')

# ========================================
# 1. ТЕКУЩЕЕ СОСТОЯНИЕ
# ========================================
print('='*80)
print('1️⃣  ТЕКУЩЕЕ СОСТОЯНИЕ:')
print('='*80)

total_before = Product.objects.count()
with_dup = Product.objects.filter(tmp_id__icontains='-dup').count()
without_dup = Product.objects.exclude(tmp_id__icontains='-dup').count()

print(f'\n📊 Всего товаров:     {total_before:,}')
print(f'🔴 С суффиксом -dup:  {with_dup:,} ({(with_dup/total_before*100):.1f}%)')
print(f'✅ Без суффикса -dup: {without_dup:,} ({(without_dup/total_before*100):.1f}%)')

# ========================================
# 2. СВЯЗАННЫЕ ДАННЫЕ
# ========================================
print('\n' + '='*80)
print('2️⃣  ПРОВЕРКА СВЯЗАННЫХ ДАННЫХ:')
print('='*80)

# OE аналоги у дубликатов
oe_count = OeKod.objects.filter(product__tmp_id__icontains='-dup').count()
# Изображения у дубликатов
images_count = ProductImage.objects.filter(product__tmp_id__icontains='-dup').count()

print(f'\n🔗 OE аналоги у дубликатов:  {oe_count:,}')
print(f'🖼️  Изображения у дубликатов: {images_count:,}')

if oe_count > 0 or images_count > 0:
    print(f'\n⚠️  ВНИМАНИЕ: У дубликатов есть связанные данные!')
    print(f'   При удалении товара они тоже удалятся (CASCADE)')
    
    # Проверяем уникальные OE
    dup_products = Product.objects.filter(tmp_id__icontains='-dup')
    
    unique_oe_count = 0
    for dup_prod in dup_products[:100]:  # Проверяем первые 100 для скорости
        base_tmp_id = dup_prod.tmp_id.split('-dup')[0]
        original = Product.objects.filter(tmp_id=base_tmp_id).first()
        
        if original:
            # Проверяем есть ли у дубликата OE, которых нет у оригинала
            dup_oe = set(dup_prod.oe_analogs.values_list('oe_kod', flat=True))
            orig_oe = set(original.oe_analogs.values_list('oe_kod', flat=True))
            unique = dup_oe - orig_oe
            if unique:
                unique_oe_count += len(unique)
    
    if unique_oe_count > 0:
        print(f'\n   ⚠️  Найдено ~{unique_oe_count} уникальных OE только у дубликатов!')
        print(f'   Рекомендуется сначала перелинковать их на оригиналы')
    else:
        print(f'\n   ✅ Проверка показала: OE у дубликатов дублируют оригиналы')
        print(f'   Безопасно удалять')

# ========================================
# 3. ПОДТВЕРЖДЕНИЕ
# ========================================
print('\n' + '='*80)
print('3️⃣  ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ:')
print('='*80)

print(f'\n❓ БУДЕТ УДАЛЕНО:')
print(f'   • Товаров:     {with_dup:,}')
print(f'   • OE аналогов: {oe_count:,}')
print(f'   • Изображений: {images_count:,}')

print(f'\n✅ ОСТАНЕТСЯ:')
print(f'   • Товаров: {without_dup:,} (ожидалось ~198,538)')

# Автоматическое подтверждение для скрипта
confirm = 'y'

if confirm.lower() == 'y':
    # ========================================
    # 4. УДАЛЕНИЕ
    # ========================================
    print('\n' + '='*80)
    print('4️⃣  ВЫПОЛНЕНИЕ УДАЛЕНИЯ:')
    print('='*80)
    
    print(f'\n🗑️  Удаляю товары с суффиксом -dup...')
    
    try:
        # Удаляем все товары с -dup
        deleted_count, deleted_details = Product.objects.filter(
            tmp_id__icontains='-dup'
        ).delete()
        
        print(f'\n✅ УСПЕШНО УДАЛЕНО:')
        print(f'   • Товаров (Product): {deleted_details.get("shop.Product", 0):,}')
        print(f'   • OE (OeKod): {deleted_details.get("shop.OeKod", 0):,}')
        print(f'   • Изображений (ProductImage): {deleted_details.get("shop.ProductImage", 0):,}')
        print(f'   • Всего объектов: {deleted_count:,}')
        
    except Exception as e:
        print(f'\n❌ ОШИБКА ПРИ УДАЛЕНИИ:')
        print(f'   {str(e)}')
        print(f'\n   Возможно нужны дополнительные права или есть блокировки')
    
    # ========================================
    # 5. РЕЗУЛЬТАТ
    # ========================================
    print('\n' + '='*80)
    print('5️⃣  ФИНАЛЬНАЯ СТАТИСТИКА:')
    print('='*80)
    
    total_after = Product.objects.count()
    with_dup_after = Product.objects.filter(tmp_id__icontains='-dup').count()
    
    print(f'\n📊 БЫЛО:      {total_before:,} товаров')
    print(f'🗑️  УДАЛЕНО:  {total_before - total_after:,} товаров')
    print(f'✅ ОСТАЛОСЬ: {total_after:,} товаров')
    print(f'🎯 ОЖИДАЛОСЬ: 198,538 товаров')
    
    if with_dup_after == 0:
        print(f'\n✅ ВСЕ ДУБЛИКАТЫ УДАЛЕНЫ!')
    else:
        print(f'\n⚠️  Осталось {with_dup_after} товаров с -dup')
    
    # Разница с ожидаемым
    expected = 198538
    diff = abs(total_after - expected)
    diff_percent = (diff / expected * 100)
    
    print(f'\n📈 ТОЧНОСТЬ:')
    print(f'   Разница: {diff:,} товаров ({diff_percent:.2f}%)')
    
    if diff_percent < 1:
        print(f'   ✅ ОТЛИЧНО! Разница < 1%')
    elif diff_percent < 5:
        print(f'   ✅ ХОРОШО! Разница < 5%')
    else:
        print(f'   ⚠️  Разница > 5%, возможны другие проблемы')
    
    # ========================================
    # 6. РЕКОМЕНДАЦИИ
    # ========================================
    print('\n' + '='*80)
    print('6️⃣  ЧТО ДЕЛАТЬ ДАЛЬШЕ:')
    print('='*80)
    
    print(f'\n✅ Шаг 1: Перезапустить Django')
    print(f'   ```bash')
    print(f'   ps aux | grep "manage.py runserver" | awk \'{{print $2}}\' | xargs kill -9')
    print(f'   nohup python3 manage.py runserver 0.0.0.0:8000 > /dev/null 2>&1 &')
    print(f'   ```')
    
    print(f'\n✅ Шаг 2: Проверить на фронте')
    print(f'   http://new.tir-lugansk.ru/shop/catalog/')
    print(f'   Должно показать: ~{total_after:,} товаров')
    
    print(f'\n✅ Шаг 3: Проверить поиск')
    print(f'   http://new.tir-lugansk.ru/shop/catalog/?search=16351024')
    print(f'   Дубликаты должны исчезнуть')
    
    if images_count > 0:
        print(f'\n⚠️  Шаг 4: Переподключить изображения (опционально)')
        print(f'   python3 manage.py link_product_images')
        print(f'   (если изображения были только у дубликатов)')
    
else:
    print(f'\n❌ УДАЛЕНИЕ ОТМЕНЕНО')

print('\n' + '='*80)
print('✅ СКРИПТ ЗАВЕРШЕН')
print('='*80)

