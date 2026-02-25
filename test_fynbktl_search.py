#!/usr/bin/env python3
"""
Проверка поиска по OE номеру: fynbktl (английская раскладка)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import OeKod, Product
from django.db.models import Q

print("╔════════════════════════════════════════════════════════════╗")
print("║    🔍 ПРОВЕРКА ПОИСКА ПО OE: fynbktl (английский)         ║")
print("╚════════════════════════════════════════════════════════════╝")

test_search = "fynbktl"

# ═══════════════════════════════════════════════════════════════
# ШАГ 1: ПРОВЕРКА ЛОГИКИ clean_number
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("ШАГ 1: Проверка clean_number()")
print("═"*60)

cleaned = Product.clean_number(test_search)
print(f"   Входной запрос: '{test_search}'")
print(f"   После clean_number(): '{cleaned}'")

if cleaned == test_search.lower():
    print(f"   ✅ Английские буквы СОХРАНЕНЫ!")
else:
    print(f"   ❌ ОШИБКА: '{test_search}' → '{cleaned}'")

# ═══════════════════════════════════════════════════════════════
# ШАГ 2: ПРОВЕРКА ЛОГИКИ is_number_search
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("ШАГ 2: Проверка is_number_search()")
print("═"*60)

is_number = OeKod.is_number_search(test_search)
print(f"   Запрос: '{test_search}'")
print(f"   is_number_search(): {is_number}")

if is_number:
    print(f"   ✅ Распознан как НОМЕР!")
else:
    print(f"   ❌ ОШИБКА: Распознан как ТЕКСТ!")
    print(f"   Причина: недостаточно цифр (нужно >= 3)")

# ═══════════════════════════════════════════════════════════════
# ШАГ 3: ПРОВЕРКА НАЛИЧИЯ В БАЗЕ
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("ШАГ 3: Поиск в таблице OeKod")
print("═"*60)

# Поиск по oe_kod (как записано в файле)
oe_by_kod = OeKod.objects.filter(oe_kod__iexact=test_search).first()
if oe_by_kod:
    print(f"   ✅ Найдено по oe_kod:")
    print(f"      ID: {oe_by_kod.id_oe}")
    print(f"      oe_kod: '{oe_by_kod.oe_kod}'")
    print(f"      oe_kod_clean: '{oe_by_kod.oe_kod_clean}'")
    print(f"      Товар: {oe_by_kod.product.tmp_id if oe_by_kod.product else 'НЕТ'}")
else:
    print(f"   ❌ НЕ найдено по oe_kod = '{test_search}'")

# Поиск по oe_kod_clean (очищенное)
oe_by_clean = OeKod.objects.filter(oe_kod_clean__iexact=cleaned).first()
if oe_by_clean:
    print(f"\n   ✅ Найдено по oe_kod_clean:")
    print(f"      ID: {oe_by_clean.id_oe}")
    print(f"      oe_kod: '{oe_by_clean.oe_kod}'")
    print(f"      oe_kod_clean: '{oe_by_clean.oe_kod_clean}'")
    print(f"      Товар: {oe_by_clean.product.tmp_id if oe_by_clean.product else 'НЕТ'}")
else:
    print(f"\n   ❌ НЕ найдено по oe_kod_clean = '{cleaned}'")

# Поиск содержит (для проверки)
oe_contains = OeKod.objects.filter(oe_kod__icontains='fyn').first()
if oe_contains:
    print(f"\n   ℹ️  Найдено по oe_kod__icontains='fyn':")
    print(f"      oe_kod: '{oe_contains.oe_kod}'")
    print(f"      oe_kod_clean: '{oe_contains.oe_kod_clean}'")

# ═══════════════════════════════════════════════════════════════
# ШАГ 4: ПРОВЕРКА ПОИСКА ТОВАРОВ (КАК НА ФРОНТЕ)
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("ШАГ 4: Поиск товаров через oe_analogs (как на фронте)")
print("═"*60)

# Имитируем логику из CatalogView
if OeKod.is_number_search(test_search):
    search_clean = Product.clean_number(test_search)
    
    print(f"   Поисковый запрос: '{test_search}'")
    print(f"   Очищенный: '{search_clean}'")
    
    # Поиск товаров
    found_products = Product.objects.filter(
        Q(oe_analogs__oe_kod_clean__iexact=search_clean)
    ).select_related('brand', 'category').distinct()
    
    count = found_products.count()
    print(f"\n   Результат: {count} товар(ов)")
    
    if count > 0:
        print(f"\n   ✅ ТОВАРЫ НАЙДЕНЫ:")
        for i, p in enumerate(found_products[:5], 1):
            print(f"      {i}. [{p.tmp_id}] {p.name[:60]}")
            # Показываем OE для этого товара
            oe_for_product = p.oe_analogs.filter(
                oe_kod_clean__iexact=search_clean
            ).first()
            if oe_for_product:
                print(f"         OE: {oe_for_product.oe_kod} (clean: {oe_for_product.oe_kod_clean})")
    else:
        print(f"\n   ❌ ТОВАРЫ НЕ НАЙДЕНЫ!")
else:
    print(f"   ⚠️ Запрос '{test_search}' НЕ распознан как номер!")
    print(f"   Поиск пойдет по тексту (названия товаров)")

# ═══════════════════════════════════════════════════════════════
# ШАГ 5: СТАТИСТИКА OE С ЛАТИНИЦЕЙ
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("ШАГ 5: Статистика OE номеров")
print("═"*60)

total_oe = OeKod.objects.count()
with_latin = OeKod.objects.filter(oe_kod__regex=r'[a-zA-Z]').count()
with_cyrillic = OeKod.objects.filter(oe_kod__regex=r'[а-яА-ЯёЁ]').count()

print(f"   Всего OE: {total_oe:,}")
print(f"   С латиницей: {with_latin:,} ({with_latin/total_oe*100:.1f}%)")
print(f"   С кириллицей: {with_cyrillic:,} ({with_cyrillic/total_oe*100:.1f}%)")

# ═══════════════════════════════════════════════════════════════
# ФИНАЛЬНЫЙ ВЕРДИКТ
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("📋 ФИНАЛЬНЫЙ ВЕРДИКТ:")
print("═"*60)

issues = []

# Проверка 1: clean_number сохраняет латиницу
if cleaned != test_search.lower():
    issues.append(f"❌ clean_number() НЕ сохраняет латиницу: '{test_search}' → '{cleaned}'")

# Проверка 2: is_number_search распознает как номер
if not is_number:
    issues.append(f"❌ is_number_search() НЕ распознает '{test_search}' как номер (нет цифр!)")

# Проверка 3: OE есть в базе
if not oe_by_clean and not oe_by_kod:
    issues.append(f"❌ OE '{test_search}' НЕ найден в базе!")

# Проверка 4: Поиск находит товары
if oe_by_clean and found_products.count() == 0:
    issues.append(f"❌ OE найден в базе, но товары НЕ найдены через поиск!")

if issues:
    print("\n🚨 ОБНАРУЖЕНЫ ПРОБЛЕМЫ:\n")
    for issue in issues:
        print(f"   {issue}")
    
    print("\n📝 РЕШЕНИЯ:")
    
    if not is_number:
        print(f"""
   1. ПРОБЛЕМА: '{test_search}' не распознается как номер (нет цифр)
   
   РЕШЕНИЕ:
   В файле oe_nomer.DBF должны быть номера с цифрами!
   Примеры правильных OE номеров:
   • fynbktl509 ✅ (есть цифры 509)
   • антилед123 ✅ (есть цифры 123)
   • fynbktl ❌ (нет цифр!)
   
   Если в файле действительно записано "fynbktl" без цифр,
   это ТЕКСТ, а не номер детали!
""")
    
    if not oe_by_clean and not oe_by_kod:
        print(f"""
   2. ПРОБЛЕМА: OE '{test_search}' отсутствует в базе
   
   РЕШЕНИЕ:
   • Проверить файл oe_nomer.DBF - есть ли там этот номер?
   • Если есть - переимпортировать:
     python3 manage.py import_oe_analogs_dbf path/to/oe_nomer.DBF --clear-existing
""")

else:
    print(f"""
✅ ВСЕ ОТЛИЧНО! Поиск по '{test_search}' работает корректно!

📊 Результаты:
   • clean_number() сохраняет латиницу: ✅
   • is_number_search() распознает как номер: ✅
   • OE найден в базе: ✅
   • Поиск находит товары: ✅

🌐 Проверить на фронте:
   http://new.tir-lugansk.ru/shop/catalog/?search={test_search}

💡 Инструкция для заказчика:
   1. Зайти на сайт
   2. Ввести в поиск: "{test_search}"
   3. Система найдет товары с этим OE номером
""")

print("═"*60)

