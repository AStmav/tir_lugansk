#!/usr/bin/env python3
"""
Проверка конкретного OE номера с известными данными:
- ID бренда: 00000002060
- ID товара: 000182541
- OE номер: fynbktl
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import OeKod, Product, Brand
from django.db.models import Q

print("╔════════════════════════════════════════════════════════════╗")
print("║    🔍 ПРОВЕРКА КОНКРЕТНОГО OE: fynbktl                    ║")
print("╚════════════════════════════════════════════════════════════╝")

# Данные из запроса
id_brend = "00000002060"
id_tovar = "000182541"
oe_name = "fynbktl"

print(f"\n📋 ИСХОДНЫЕ ДАННЫЕ:")
print(f"   ID_BRENB: {id_brend}")
print(f"   ID_TOVAR: {id_tovar}")
print(f"   NAME: {oe_name}")

# ═══════════════════════════════════════════════════════════════
# ПРОВЕРКА 1: БРЕНД
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("ПРОВЕРКА 1: Есть ли бренд в базе?")
print("═"*60)

brand = Brand.objects.filter(code=id_brend).first()
if brand:
    print(f"   ✅ БРЕНД НАЙДЕН:")
    print(f"      ID в Django: {brand.id}")
    print(f"      code: {brand.code}")
    print(f"      name: {brand.name}")
else:
    print(f"   ❌ БРЕНД НЕ НАЙДЕН! code='{id_brend}'")
    print(f"\n   Проверим похожие бренды:")
    similar_brands = Brand.objects.filter(code__icontains="002060")[:5]
    if similar_brands.exists():
        for b in similar_brands:
            print(f"      • code='{b.code}' name='{b.name}'")
    else:
        print(f"      Нет похожих брендов")
    
    print(f"\n   ⚠️ ПРИЧИНА ПРОПУСКА ПРИ ИМПОРТЕ:")
    print(f"      При импорте OE с ID_BRENB='{id_brend}' система не нашла бренд")
    print(f"      Но OE все равно импортируется с brand=None!")

# ═══════════════════════════════════════════════════════════════
# ПРОВЕРКА 2: ТОВАР
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("ПРОВЕРКА 2: Есть ли товар в базе?")
print("═"*60)

product = Product.objects.filter(tmp_id=id_tovar).first()
if product:
    print(f"   ✅ ТОВАР НАЙДЕН:")
    print(f"      ID в Django: {product.id}")
    print(f"      tmp_id: {product.tmp_id}")
    print(f"      name: {product.name[:60]}")
    print(f"      catalog_number: {product.catalog_number}")
    print(f"      catalog_number_clean: {product.catalog_number_clean}")
else:
    print(f"   ❌ ТОВАР НЕ НАЙДЕН! tmp_id='{id_tovar}'")
    
    # Проверим с суффиксом
    product_with_suffix = Product.objects.filter(tmp_id__startswith=id_tovar).first()
    if product_with_suffix:
        print(f"\n   ℹ️ Найден товар с суффиксом:")
        print(f"      tmp_id: {product_with_suffix.tmp_id}")
        print(f"      name: {product_with_suffix.name[:60]}")
    else:
        print(f"\n   Проверим похожие товары:")
        similar = Product.objects.filter(tmp_id__icontains="182541")[:3]
        if similar.exists():
            for p in similar:
                print(f"      • tmp_id='{p.tmp_id}'")
        else:
            print(f"      Нет похожих товаров")
    
    print(f"\n   ❌ КРИТИЧЕСКАЯ ПРИЧИНА ПРОПУСКА:")
    print(f"      При импорте OE с ID_TOVAR='{id_tovar}' система НЕ НАШЛА товар!")
    print(f"      OE НЕ ИМПОРТИРУЕТСЯ БЕЗ ТОВАРА!")
    print(f"\n   📝 РЕШЕНИЕ:")
    print(f"      1. Сначала импортировать товары: import_dbf 1C181225.DBF")
    print(f"      2. Потом импортировать OE: import_oe_analogs_dbf oe_nomer.DBF")

# ═══════════════════════════════════════════════════════════════
# ПРОВЕРКА 3: OE В БАЗЕ
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("ПРОВЕРКА 3: Есть ли OE в базе?")
print("═"*60)

# Поиск по oe_kod
oe_by_name = OeKod.objects.filter(oe_kod__iexact=oe_name).first()
if oe_by_name:
    print(f"   ✅ OE НАЙДЕН ПО oe_kod:")
    print(f"      id_oe: {oe_by_name.id_oe}")
    print(f"      oe_kod: '{oe_by_name.oe_kod}'")
    print(f"      oe_kod_clean: '{oe_by_name.oe_kod_clean}'")
    print(f"      id_tovar: {oe_by_name.id_tovar}")
    print(f"      Товар: {oe_by_name.product.tmp_id if oe_by_name.product else 'НЕТ'}")
    print(f"      Бренд: {oe_by_name.brand.name if oe_by_name.brand else 'НЕТ'}")
else:
    print(f"   ❌ OE НЕ НАЙДЕН по oe_kod='{oe_name}'")

# Поиск по id_tovar
oe_by_tovar = OeKod.objects.filter(id_tovar=id_tovar).first()
if oe_by_tovar:
    print(f"\n   ✅ Найден OE для товара {id_tovar}:")
    print(f"      oe_kod: '{oe_by_tovar.oe_kod}'")
    print(f"      oe_kod_clean: '{oe_by_tovar.oe_kod_clean}'")
else:
    print(f"\n   ❌ OE для товара {id_tovar} НЕ НАЙДЕН")

# Поиск похожих
oe_similar = OeKod.objects.filter(oe_kod__icontains="fyn")[:5]
if oe_similar.exists():
    print(f"\n   ℹ️ Похожие OE номера (содержат 'fyn'):")
    for oe in oe_similar:
        print(f"      • '{oe.oe_kod}' → '{oe.oe_kod_clean}' (товар: {oe.product.tmp_id if oe.product else 'НЕТ'})")

# ═══════════════════════════════════════════════════════════════
# ПРОВЕРКА 4: ЛОГИКА clean_number
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("ПРОВЕРКА 4: Логика clean_number()")
print("═"*60)

cleaned = Product.clean_number(oe_name)
print(f"   Вход: '{oe_name}'")
print(f"   Выход: '{cleaned}'")

if cleaned == oe_name.lower():
    print(f"   ✅ Английские буквы сохранены")
else:
    print(f"   ⚠️ Преобразование: '{oe_name}' → '{cleaned}'")

# ═══════════════════════════════════════════════════════════════
# ПРОВЕРКА 5: ЛОГИКА is_number_search
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("ПРОВЕРКА 5: Логика is_number_search()")
print("═"*60)

is_number = OeKod.is_number_search(oe_name)
print(f"   Запрос: '{oe_name}'")
print(f"   is_number_search(): {is_number}")

if is_number:
    print(f"   ✅ Распознан как НОМЕР")
else:
    print(f"   ❌ Распознан как ТЕКСТ!")
    print(f"\n   ПРИЧИНА:")
    digit_count = sum(1 for c in oe_name if c.isdigit())
    alpha_count = sum(1 for c in oe_name if c.isalpha())
    print(f"      Букв: {alpha_count}, Цифр: {digit_count}")
    print(f"      Требуется: >= 3 цифры")
    print(f"\n   ⚠️ '{oe_name}' будет искаться как ТЕКСТ (в названиях товаров)!")

# ═══════════════════════════════════════════════════════════════
# ПРОВЕРКА 6: ПОИСК (имитация фронта)
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("ПРОВЕРКА 6: Поиск товаров (как на фронте)")
print("═"*60)

if product:  # Если товар найден
    print(f"   Проверяем связь товар → OE аналоги:")
    oe_count = product.oe_analogs.count()
    print(f"   Количество OE у товара: {oe_count}")
    
    if oe_count > 0:
        print(f"\n   OE аналоги товара:")
        for oe in product.oe_analogs.all()[:10]:
            print(f"      • '{oe.oe_kod}' (clean: '{oe.oe_kod_clean}')")

# Имитация поиска из CatalogView
if OeKod.is_number_search(oe_name):
    search_clean = Product.clean_number(oe_name)
    print(f"\n   Поиск как НОМЕР:")
    print(f"   Очищенный запрос: '{search_clean}'")
    
    found = Product.objects.filter(
        Q(oe_analogs__oe_kod_clean__iexact=search_clean)
    ).distinct()
    
    print(f"   Найдено товаров: {found.count()}")
    
    if found.exists():
        print(f"   ✅ ТОВАРЫ НАЙДЕНЫ:")
        for p in found[:3]:
            print(f"      • [{p.tmp_id}] {p.name[:50]}")
    else:
        print(f"   ❌ ТОВАРЫ НЕ НАЙДЕНЫ")
else:
    print(f"\n   Поиск как ТЕКСТ:")
    print(f"   Ищем в названиях товаров...")
    
    found_text = Product.objects.filter(
        Q(name__icontains=oe_name)
    )[:5]
    
    print(f"   Найдено: {found_text.count()}")

# ═══════════════════════════════════════════════════════════════
# ФИНАЛЬНЫЙ ВЕРДИКТ
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print("📋 ФИНАЛЬНЫЙ ВЕРДИКТ:")
print("═"*60)

issues = []
solutions = []

# Проверка товара
if not product:
    issues.append(f"❌ Товар {id_tovar} НЕ НАЙДЕН в базе!")
    solutions.append(f"1. Импортировать товары: python3 manage.py import_dbf 1C181225.DBF")

# Проверка OE
if not oe_by_name and not oe_by_tovar:
    issues.append(f"❌ OE '{oe_name}' НЕ НАЙДЕН в базе!")
    if not product:
        solutions.append(f"2. После импорта товаров → импортировать OE: python3 manage.py import_oe_analogs_dbf oe_nomer.DBF")

# Проверка is_number_search
if not is_number:
    issues.append(f"❌ '{oe_name}' НЕ распознается как номер (нет цифр)!")
    solutions.append(f"3. ПРОБЛЕМА: В OE номере '{oe_name}' нет цифр!")
    solutions.append(f"   Это редкий случай. Обычно OE номера содержат цифры:")
    solutions.append(f"   • fynbktl509 ✅")
    solutions.append(f"   • антилед123 ✅")
    solutions.append(f"   • fynbktl ❌ (нет цифр)")

# Проверка бренда
if not brand:
    issues.append(f"⚠️ Бренд {id_brend} не найден (некритично)")

if issues:
    print(f"\n🚨 ОБНАРУЖЕНЫ ПРОБЛЕМЫ:\n")
    for issue in issues:
        print(f"   {issue}")
    
    if solutions:
        print(f"\n📝 РЕШЕНИЯ:\n")
        for solution in solutions:
            print(f"   {solution}")
else:
    print(f"\n✅ ВСЕ В ПОРЯДКЕ!")
    print(f"   • Бренд найден: ✅")
    print(f"   • Товар найден: ✅")
    print(f"   • OE импортирован: ✅")
    print(f"   • Поиск работает: ✅")

print(f"\n{'═'*60}")
print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
print("═"*60)

