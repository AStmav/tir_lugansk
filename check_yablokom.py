#!/usr/bin/env python3
"""
Проверка поиска по OE номеру: яблоком168
Запуск: python3 check_yablokom.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import OeKod, Product
from django.db.models import Q

print("╔════════════════════════════════════════════════════════════╗")
print("║       🔍 ПРОВЕРКА ПОИСКА: яблоком168                      ║")
print("╚════════════════════════════════════════════════════════════╝")

search_term = "яблоком168"
print(f"\n📝 Поисковый запрос: \"{search_term}\"")

# 1. Проверяем наличие OE с таким номером
print(f"\n{'═'*60}")
print("1️⃣  ПОИСК В ТАБЛИЦЕ OeKod:")
print("═"*60)

oe_results = OeKod.objects.filter(oe_kod_clean__iexact=search_term)
oe_count = oe_results.count()

print(f"   Найдено OE аналогов: {oe_count}")

if oe_count > 0:
    print(f"\n   ✅ OE номера найдены:")
    for i, oe in enumerate(oe_results[:5], 1):
        product_name = oe.product.name[:50] if oe.product else "НЕТ ТОВАРА"
        brand_name = oe.brand.name if oe.brand else "НЕТ БРЕНДА"
        print(f"      {i}. {oe.oe_kod:25s} → товар: {oe.product.tmp_id if oe.product else 'N/A'}")
        print(f"         Бренд: {brand_name}, Товар: {product_name}")
else:
    print(f"   ❌ OE аналоги НЕ НАЙДЕНЫ!")
    print(f"\n   Проверим похожие:")
    similar = OeKod.objects.filter(oe_kod_clean__icontains="яблоко")[:5]
    if similar.exists():
        for oe in similar:
            print(f"      • \"{oe.oe_kod_clean}\" ({oe.oe_kod})")
    else:
        print(f"      Ничего похожего не найдено")

# 2. Поиск товаров через связь oe_analogs (как в CatalogView)
print(f"\n{'═'*60}")
print("2️⃣  ПОИСК ТОВАРОВ ЧЕРЕЗ oe_analogs (как на фронте):")
print("═"*60)

found_products = Product.objects.filter(
    Q(oe_analogs__oe_kod_clean__iexact=search_term)
).select_related('brand', 'category').distinct()

product_count = found_products.count()
print(f"   Найдено товаров: {product_count}")

if product_count > 0:
    print(f"\n   ✅ ТОВАРЫ НАЙДЕНЫ:")
    for i, p in enumerate(found_products[:5], 1):
        print(f"      {i}. [{p.tmp_id}] {p.name[:60]}")
        # Показываем OE для этого товара
        oe_for_product = p.oe_analogs.filter(oe_kod_clean__iexact=search_term).first()
        if oe_for_product:
            print(f"         OE: {oe_for_product.oe_kod} (clean: {oe_for_product.oe_kod_clean})")
else:
    print(f"   ❌ ТОВАРЫ НЕ НАЙДЕНЫ!")

# 3. Проверка конкретного OE из админки
print(f"\n{'═'*60}")
print("3️⃣  ПРОВЕРКА OE ИЗ АДМИНКИ (ID: 00000376513):")
print("═"*60)

admin_oe = OeKod.objects.filter(id_oe="00000376513").first()
if admin_oe:
    print(f"   ✅ OE из админки найден:")
    print(f"      ID: {admin_oe.id_oe}")
    print(f"      oe_kod: \"{admin_oe.oe_kod}\"")
    print(f"      oe_kod_clean: \"{admin_oe.oe_kod_clean}\"")
    print(f"      Товар: {admin_oe.product.tmp_id if admin_oe.product else 'НЕТ'}")
    print(f"      ID товара: {admin_oe.id_tovar}")
    
    # Проверяем совпадает ли с поисковым запросом
    if admin_oe.oe_kod_clean.lower() == search_term.lower():
        print(f"\n      ✅ Совпадает с поисковым запросом!")
    else:
        print(f"\n      ⚠️ НЕ совпадает! В админке: \"{admin_oe.oe_kod_clean}\"")
        print(f"         Искали: \"{search_term}\"")
else:
    print(f"   ❌ OE с ID 00000376513 НЕ НАЙДЕН в базе!")

# 4. Статистика
print(f"\n{'═'*60}")
print("📊 ОБЩАЯ СТАТИСТИКА:")
print("═"*60)

total_oe = OeKod.objects.count()
total_products = Product.objects.count()
products_with_oe = Product.objects.filter(oe_analogs__isnull=False).distinct().count()
oe_with_clean = OeKod.objects.exclude(oe_kod_clean="").count()

print(f"   Всего OE аналогов в базе: {total_oe:,}")
print(f"   OE с заполненным oe_kod_clean: {oe_with_clean:,}")
print(f"   Всего товаров в базе: {total_products:,}")
print(f"   Товаров с OE аналогами: {products_with_oe:,}")

# ВЕРДИКТ
print(f"\n{'═'*60}")
print("📋 ВЕРДИКТ:")
print("═"*60)

if oe_count > 0 and product_count > 0:
    print(f"""
✅ ПОИСК ПО OE РАБОТАЕТ!
   • Найдено OE: {oe_count}
   • Найдено товаров: {product_count}

🌐 Проверить на фронте:
   http://new.tir-lugansk.ru/shop/catalog/?search=яблоком168
   http://new.tir-lugansk.ru/shop/catalog/?search=Яблоко+M16/8

💡 Инструкция для заказчика:
   1. Зайти на http://new.tir-lugansk.ru/shop/catalog/
   2. Ввести в поиск: "яблоком168" или "Яблоко M16/8"
   3. Система автоматически найдет товары с этим OE номером
   
   ВАЖНО: Вводить на КИРИЛЛИЦЕ! Если ввести "yablokom168" (латиницей) - не найдет!
""")

elif oe_count > 0 and product_count == 0:
    print(f"""
⚠️ ПРОБЛЕМА: OE найдены ({oe_count}), но товары НЕ найдены!
   
   Возможная причина: связь OeKod → Product сломана
   
   Решение:
   1. Проверить в админке, что у OE есть связь с товаром
   2. Перезапустить импорт: python3 manage.py import_oe_analogs_dbf oe_nomer.DBF --clear-existing
""")

elif oe_count == 0:
    print(f"""
❌ ПРОБЛЕМА: OE аналоги с номером "яблоком168" НЕ НАЙДЕНЫ!
""")
    
    if total_oe == 0:
        print(f"""
   КРИТИЧНО: В базе вообще нет OE аналогов!
   
   Решение:
   python3 manage.py import_oe_analogs_dbf path/to/oe_nomer.DBF
""")
    else:
        print(f"""
   В базе есть {total_oe:,} OE, но "яблоком168" среди них нет
   
   Возможные причины:
   1. Файл oe_nomer.DBF не содержит этот номер
   2. При импорте произошла ошибка
   3. Номер записан по-другому
   
   Решение:
   1. Проверить файл oe_nomer.DBF
   2. Повторить импорт с логами
""")

print("="*60)

