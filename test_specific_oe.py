#!/usr/bin/env python3
"""
Тест поиска конкретного OE номера из админки
OE: Яблоко M16/8 → яблоком168
ID: 00000376513
Товар: 000195707
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import OeKod, Product
from django.db.models import Q

print("╔════════════════════════════════════════════════════════════╗")
print("║      🧪 ТЕСТ ПОИСКА КОНКРЕТНОГО OE НОМЕРА                 ║")
print("╚════════════════════════════════════════════════════════════╝")

# Данные из админки
test_id_oe = "00000376513"
test_oe_kod = "Яблоко M16/8"
test_oe_clean = "яблоком168"
test_id_tovar = "000195707"

print(f"\n📋 ТЕСТОВЫЕ ДАННЫЕ:")
print(f"   ID аналога: {test_id_oe}")
print(f"   OE номер: {test_oe_kod}")
print(f"   OE (очищенный): {test_oe_clean}")
print(f"   ID товара: {test_id_tovar}")

# 1. Проверяем существование в базе
print(f"\n{'═'*62}")
print(f"1️⃣  ПРОВЕРКА СУЩЕСТВОВАНИЯ В БАЗЕ:")
print(f"{'═'*62}")

oe_by_id = OeKod.objects.filter(id_oe=test_id_oe).first()
if oe_by_id:
    print(f"   ✅ OE найден по ID: {oe_by_id.id_oe}")
    print(f"      oe_kod: '{oe_by_id.oe_kod}'")
    print(f"      oe_kod_clean: '{oe_by_id.oe_kod_clean}'")
    print(f"      Товар: {oe_by_id.product.tmp_id if oe_by_id.product else 'НЕТ'}")
    print(f"      Бренд: {oe_by_id.brand.name if oe_by_id.brand else 'НЕТ'}")
else:
    print(f"   ❌ OE НЕ НАЙДЕН в базе!")
    print(f"   Проверим все OE с похожим номером:")
    similar = OeKod.objects.filter(
        Q(oe_kod__icontains="Яблоко") | 
        Q(oe_kod_clean__icontains="яблоко")
    )[:5]
    for oe in similar:
        print(f"      • {oe.oe_kod} → {oe.oe_kod_clean}")

# 2. Тест поиска по очищенному номеру (КИРИЛЛИЦА)
print(f"\n{'═'*62}")
print(f"2️⃣  ПОИСК ПО ОЧИЩЕННОМУ НОМЕРУ (кириллица):")
print(f"{'═'*62}")
print(f"   Ищем: '{test_oe_clean}'")

found_products = Product.objects.filter(
    Q(oe_analogs__oe_kod_clean__iexact=test_oe_clean)
).distinct()

if found_products.exists():
    print(f"   ✅ НАЙДЕНО товаров: {found_products.count()}")
    for p in found_products[:3]:
        print(f"      • {p.tmp_id} - {p.name[:60]}")
else:
    print(f"   ❌ НИЧЕГО НЕ НАЙДЕНО!")

# 3. Тест поиска по латинице (как может вводить пользователь)
print(f"\n{'═'*62}")
print(f"3️⃣  ПОИСК ПО ЛАТИНИЦЕ (как вводит пользователь):")
print(f"{'═'*62}")

test_latin_variants = [
    "yablokom168",
    "YABLOKOM168",
    "Yabloko M16/8",
    "yabloko m16/8"
]

for search_term in test_latin_variants:
    # Очищаем как в views.py
    from shop.models import Product as Prod
    search_clean = Prod.clean_number(search_term)
    
    print(f"\n   Ввод: '{search_term}' → очищенный: '{search_clean}'")
    
    found = Product.objects.filter(
        Q(oe_analogs__oe_kod_clean__iexact=search_clean)
    ).distinct()
    
    if found.exists():
        print(f"   ✅ Найдено: {found.count()} товар(ов)")
    else:
        print(f"   ❌ Не найдено (кириллица ≠ латиница!)")

# 4. Проверка товара по ID
print(f"\n{'═'*62}")
print(f"4️⃣  ПРОВЕРКА ТОВАРА ПО ID:")
print(f"{'═'*62}")

product = Product.objects.filter(tmp_id=test_id_tovar).first()
if product:
    print(f"   ✅ Товар найден: {product.tmp_id}")
    print(f"      Название: {product.name}")
    
    oe_count = product.oe_analogs.count()
    print(f"      OE аналогов: {oe_count}")
    
    if oe_count > 0:
        print(f"\n      Список OE:")
        for oe in product.oe_analogs.all()[:10]:
            print(f"         • {oe.oe_kod:30s} → {oe.oe_kod_clean}")
else:
    print(f"   ❌ Товар НЕ НАЙДЕН!")

# 5. Тест с исходным номером (с пробелами и знаками)
print(f"\n{'═'*62}")
print(f"5️⃣  ПОИСК С ИСХОДНЫМ НОМЕРОМ (как в админке):")
print(f"{'═'*62}")
print(f"   Ввод: '{test_oe_kod}'")

search_clean_original = Product.clean_number(test_oe_kod)
print(f"   Очищенный: '{search_clean_original}'")

found_original = Product.objects.filter(
    Q(oe_analogs__oe_kod_clean__iexact=search_clean_original)
).distinct()

if found_original.exists():
    print(f"   ✅ НАЙДЕНО: {found_original.count()} товар(ов)")
    for p in found_original[:3]:
        print(f"      • {p.tmp_id} - {p.name[:60]}")
else:
    print(f"   ❌ НИЧЕГО НЕ НАЙДЕНО!")

# ФИНАЛЬНЫЙ ВЕРДИКТ
print(f"\n{'═'*62}")
print(f"📋 ФИНАЛЬНЫЙ ВЕРДИКТ:")
print(f"{'═'*62}")

if not oe_by_id:
    print(f"""
❌ ПРОБЛЕМА: OE аналог с ID {test_id_oe} НЕ НАЙДЕН в базе!

Решение:
1. Проверить импорт: python3 manage.py shell -c "from shop.models import OeKod; print(OeKod.objects.count())"
2. Если 0 → импортировать: python3 manage.py import_oe_analogs_dbf oe_nomer.DBF
""")

elif test_oe_clean.lower() != test_oe_clean and not found_products.exists():
    print(f"""
⚠️ ПРОБЛЕМА: Регистр! В базе '{test_oe_clean}', поиск регистрозависимый?

Решение: Проверить что в views.py используется __iexact (регистронезависимый)
""")

elif 'яблоко' in test_oe_clean.lower():
    print(f"""
⚠️ ПОТЕНЦИАЛЬНАЯ ПРОБЛЕМА: Кириллица!

В базе: '{test_oe_clean}' (кириллица)
Пользователь вводит: 'yablokom168' (латиница)
Результат: НЕ НАЙДЕТ! ❌

РЕШЕНИЯ:

Вариант 1: Объяснить заказчику
   • Вводить OE номера точно как в админке: "Яблоко M16/8"
   • Система сама очистит до "яблоком168"
   • Поиск сработает! ✅

Вариант 2: Добавить транслитерацию (сложно)
   • При импорте сохранять и кириллицу, и латиницу
   • Требует доработки кода

Вариант 3: Поиск по ID товара
   • Искать по "{test_id_tovar}" (ID товара)
   • Это всегда цифры, без проблем с языком
""")

elif found_products.exists():
    print(f"""
✅ ВСЕ РАБОТАЕТ ОТЛИЧНО!

Поиск по OE номеру '{test_oe_clean}' находит {found_products.count()} товар(ов).

Как использовать:
1. Ввести в поиск: "Яблоко M16/8" или "яблоком168"
2. Система автоматически очистит номер
3. Найдет товары с этим OE

Тест на фронте:
http://new.tir-lugansk.ru/shop/catalog/?search=яблоком168
http://new.tir-lugansk.ru/shop/catalog/?search=Яблоко M16/8
""")

else:
    print(f"""
❓ НЕОПРЕДЕЛЕННАЯ СИТУАЦИЯ

OE есть в базе, но поиск не находит товары.
Проверьте связь OeKod → Product в админке.
""")

print(f"{'═'*62}")

