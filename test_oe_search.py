#!/usr/bin/env python3
"""
Скрипт для диагностики поиска по OE номерам
Запуск: python3 test_oe_search.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import OeKod, Product
from django.db.models import Q

print("╔════════════════════════════════════════════════════════════╗")
print("║         🔍 ДИАГНОСТИКА ПОИСКА ПО OE НОМЕРАМ               ║")
print("╚════════════════════════════════════════════════════════════╝")

# 1. Проверка данных
total_oe = OeKod.objects.count()
total_products = Product.objects.count()
print(f"\n📊 ДАННЫЕ В БАЗЕ:")
print(f"   OE аналогов: {total_oe:,}")
print(f"   Товаров: {total_products:,}")

if total_oe == 0:
    print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: OE аналоги не импортированы!")
    print("   Решение: python3 manage.py import_oe_analogs_dbf path/to/oe_nomer.DBF")
    exit(1)

# 2. Проверка заполнения oe_kod_clean
empty_clean = OeKod.objects.filter(oe_kod_clean='').count()
filled_clean = OeKod.objects.exclude(oe_kod_clean='').count()
print(f"\n📈 ЗАПОЛНЕНИЕ oe_kod_clean:")
print(f"   ✅ Заполнено: {filled_clean:,}")
print(f"   ❌ Пусто: {empty_clean:,}")

if empty_clean > 0:
    print(f"\n⚠️ ВНИМАНИЕ: {empty_clean} записей с пустым oe_kod_clean!")
    print(f"   Это {(empty_clean/total_oe*100):.1f}% от всех OE номеров")

# 3. Примеры OE номеров
print(f"\n🔍 ПРИМЕРЫ OE НОМЕРОВ (первые 10):")
for i, oe in enumerate(OeKod.objects.select_related('product', 'brand')[:10], 1):
    brand_name = oe.brand.name if oe.brand else "Без бренда"
    print(f"   {i:2d}. {oe.oe_kod:20s} → {oe.oe_kod_clean:20s}")
    print(f"       Товар: {oe.product.tmp_id} | Бренд: {brand_name}")

# 4. Тестовый поиск
test_oe = OeKod.objects.exclude(oe_kod_clean='').first()
search_success = False

if test_oe:
    print(f"\n{'═'*62}")
    print(f"🧪 ТЕСТОВЫЙ ПОИСК №1:")
    print(f"{'═'*62}")
    print(f"   Ищем по OE: '{test_oe.oe_kod_clean}'")
    print(f"   Исходный номер: '{test_oe.oe_kod}'")
    
    # Поиск через запрос как в CatalogView
    found = Product.objects.filter(
        Q(oe_analogs__oe_kod_clean__iexact=test_oe.oe_kod_clean)
    ).distinct()
    
    found_count = found.count()
    print(f"   Результат: {found_count} товар(ов)")
    
    if found_count > 0:
        print(f"   ✅ ПОИСК РАБОТАЕТ!")
        search_success = True
        for p in found[:3]:
            print(f"      • {p.tmp_id} - {p.name[:50]}")
    else:
        print(f"   ❌ ПОИСК НЕ НАШЕЛ ТОВАРЫ!")
        print(f"   Ожидаемый товар из OeKod:")
        print(f"      {test_oe.product.tmp_id} - {test_oe.product.name[:50]}")

# 5. Второй тест с другим OE номером
test_oe2 = OeKod.objects.exclude(oe_kod_clean='').last()
if test_oe2 and test_oe2.id != test_oe.id:
    print(f"\n{'═'*62}")
    print(f"🧪 ТЕСТОВЫЙ ПОИСК №2:")
    print(f"{'═'*62}")
    print(f"   Ищем по OE: '{test_oe2.oe_kod_clean}'")
    
    found2 = Product.objects.filter(
        Q(oe_analogs__oe_kod_clean__iexact=test_oe2.oe_kod_clean)
    ).distinct()
    
    found_count2 = found2.count()
    print(f"   Результат: {found_count2} товар(ов)")
    
    if found_count2 > 0:
        print(f"   ✅ ПОИСК РАБОТАЕТ!")
        search_success = True

# 6. Проверка связи product → oe_analogs
print(f"\n{'═'*62}")
print(f"🔗 ПРОВЕРКА СВЯЗИ product → oe_analogs:")
print(f"{'═'*62}")

product_with_oe = Product.objects.filter(oe_analogs__isnull=False).first()
if product_with_oe:
    oe_count = product_with_oe.oe_analogs.count()
    print(f"   Товар: {product_with_oe.tmp_id} - {product_with_oe.name[:50]}")
    print(f"   Количество OE аналогов: {oe_count}")
    
    if oe_count > 0:
        print(f"   ✅ Связь работает корректно!")
        print(f"\n   Примеры OE для этого товара:")
        for oe in product_with_oe.oe_analogs.all()[:5]:
            print(f"      • {oe.oe_kod} ({oe.oe_kod_clean})")
    else:
        print(f"   ❌ Связь не работает!")
else:
    print(f"   ❌ Не найдено товаров с OE аналогами!")
    print(f"   Это странно, т.к. OeKod.objects.count() = {total_oe}")

# 7. Проверка обратной связи oe → product
print(f"\n{'═'*62}")
print(f"🔗 ПРОВЕРКА СВЯЗИ oe → product:")
print(f"{'═'*62}")

random_oe = OeKod.objects.first()
if random_oe and random_oe.product:
    print(f"   OE: {random_oe.oe_kod}")
    print(f"   → Товар: {random_oe.product.tmp_id} - {random_oe.product.name[:50]}")
    print(f"   ✅ Обратная связь работает!")
else:
    print(f"   ❌ Обратная связь не работает!")

# 8. Финальный вердикт
print(f"\n{'═'*62}")
print(f"📋 ИТОГОВЫЙ ВЕРДИКТ:")
print(f"{'═'*62}")

issues = []

if total_oe == 0:
    issues.append("❌ OE аналоги не импортированы")
elif total_oe < 400000:
    issues.append(f"⚠️ Мало OE аналогов (ожидалось ~439,000, есть {total_oe:,})")

if empty_clean > total_oe * 0.1:  # Если более 10% пусты
    issues.append(f"❌ Много пустых oe_kod_clean ({empty_clean:,})")

if not search_success:
    issues.append("❌ Поиск по OE номерам НЕ РАБОТАЕТ")

if not product_with_oe:
    issues.append("❌ Связь product → oe_analogs сломана")

if issues:
    print("\n🚨 ОБНАРУЖЕНЫ ПРОБЛЕМЫ:\n")
    for issue in issues:
        print(f"   {issue}")
    
    print("\n📝 РЕКОМЕНДАЦИИ:")
    
    if total_oe == 0:
        print("""
   1. Импортируйте OE аналоги:
      python3 manage.py import_oe_analogs_dbf path/to/oe_nomer.DBF
""")
    
    if empty_clean > 0:
        print(f"""
   2. Заполните пустые oe_kod_clean ({empty_clean:,} записей):
      python3 manage.py shell
      
      from shop.models import OeKod
      batch = []
      for oe in OeKod.objects.filter(oe_kod_clean=''):
          oe.oe_kod_clean = OeKod.clean_number(oe.oe_kod)
          batch.append(oe)
          if len(batch) >= 10000:
              OeKod.objects.bulk_update(batch, ['oe_kod_clean'])
              print(f'Обновлено: {{len(batch)}}')
              batch = []
      if batch:
          OeKod.objects.bulk_update(batch, ['oe_kod_clean'])
      print('✅ Готово!')
      exit()
""")
    
    if not search_success:
        print("""
   3. Проверьте логику поиска в shop/views.py
   4. Очистите кэш и перезапустите сервер:
      find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
      sudo systemctl restart tir-lugansk
""")
    
    print(f"\n{'═'*62}")
    exit(1)

else:
    print(f"""
✅ ВСЕ ОТЛИЧНО! Поиск по OE номерам работает корректно!

📊 Статистика:
   • OE аналогов в базе: {total_oe:,}
   • Заполнено oe_kod_clean: {filled_clean:,} ({filled_clean/total_oe*100:.1f}%)
   • Связи работают корректно
   • Тестовый поиск успешен

🧪 Протестируйте на фронте:
   http://new.tir-lugansk.ru/shop/catalog/?search={test_oe.oe_kod_clean if test_oe else 'OE_NUMBER'}

💡 Как использовать:
   1. Зайти на http://new.tir-lugansk.ru/shop/catalog/
   2. Ввести OE номер в поиск (например: {test_oe.oe_kod_clean if test_oe else '5000289804'})
   3. Система найдет товары с этим OE номером
   
   Особенности:
   • Поиск работает по очищенным номерам (без пробелов, тире, точек)
   • Если ввести "5 000 289 804" или "5000289804" - найдет одинаково
""")
    print(f"{'═'*62}")
    exit(0)

