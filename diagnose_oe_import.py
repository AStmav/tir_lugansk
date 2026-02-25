#!/usr/bin/env python3
"""
Диагностика: почему OE номер мог НЕ импортироваться
"""
import os
import sys

print("╔════════════════════════════════════════════════════════════╗")
print("║    🔍 ДИАГНОСТИКА ИМПОРТА OE НОМЕРОВ                      ║")
print("╚════════════════════════════════════════════════════════════╝")

# Проверяем файл DBF
dbf_file = input("\nПуть к файлу oe_nomer.DBF: ").strip()
if not dbf_file:
    dbf_file = "media/imports/oe_nomer.DBF"

if not os.path.exists(dbf_file):
    print(f"❌ Файл не найден: {dbf_file}")
    sys.exit(1)

print(f"\n✅ Файл найден: {dbf_file}")

# Читаем DBF
try:
    from dbfread import DBF
except ImportError:
    print("❌ Модуль dbfread не установлен!")
    print("   Установите: pip install dbfread")
    sys.exit(1)

print("\n" + "═"*60)
print("ШАГ 1: Анализ структуры DBF файла")
print("═"*60)

table = DBF(dbf_file, encoding='cp1251')
total_records = len(table)

print(f"\nВсего записей в файле: {total_records:,}")

# Показываем структуру
first_record = next(iter(table))
print(f"\nПоля в файле:")
for key in first_record.keys():
    print(f"   • {key}")

# Ищем конкретный номер
print("\n" + "═"*60)
print("ШАГ 2: Поиск конкретного OE номера")
print("═"*60)

search_name = input("\nВведите OE номер для поиска (например, fynbktl): ").strip()
if not search_name:
    search_name = "fynbktl"

print(f"\nИщем записи с NAME содержащим '{search_name}'...")

found_records = []
for record_num, record in enumerate(table, start=1):
    name = str(record.get('NAME', '') or '').strip()
    
    if search_name.lower() in name.lower():
        found_records.append({
            'num': record_num,
            'id_oe': str(record.get('ID_oe', '') or record.get('ID_OE', '') or '').strip(),
            'name': name,
            'name_str': str(record.get('NAME_STR', '') or record.get('Name_STR', '') or '').strip(),
            'id_brend': str(record.get('ID_BRENB', '') or record.get('ID_BREND', '') or '').strip(),
            'id_tovar': str(record.get('ID_TOVAR', '') or record.get('ID_tovar', '') or '').strip(),
        })

if found_records:
    print(f"\n✅ Найдено записей: {len(found_records)}")
    
    for i, rec in enumerate(found_records[:10], 1):
        print(f"\n{i}. Запись #{rec['num']}:")
        print(f"   ID_oe: '{rec['id_oe']}'")
        print(f"   NAME: '{rec['name']}'")
        print(f"   NAME_STR: '{rec['name_str']}'")
        print(f"   ID_BRENB: '{rec['id_brend']}'")
        print(f"   ID_TOVAR: '{rec['id_tovar']}'")
        
        # ПРОВЕРКА ПРИЧИН ПРОПУСКА
        issues = []
        
        # Причина 1: Пустые поля
        if not rec['id_oe']:
            issues.append("❌ ID_oe ПУСТОЙ!")
        if not rec['name']:
            issues.append("❌ NAME ПУСТОЙ!")
        if not rec['id_tovar']:
            issues.append("❌ ID_TOVAR ПУСТОЙ!")
        
        # Причина 2: Служебная запись
        if rec['id_oe'].lower() in ['id_oe', 'character']:
            issues.append("❌ Служебная запись (заголовок)")
        
        if issues:
            print(f"\n   ⚠️ ПРИЧИНЫ ПРОПУСКА:")
            for issue in issues:
                print(f"      {issue}")
        else:
            print(f"\n   ✅ Запись валидна для импорта")
else:
    print(f"\n❌ Записи с NAME='{search_name}' НЕ найдены в файле!")
    
    # Показываем первые 10 записей
    print(f"\nПервые 10 записей из файла:")
    table2 = DBF(dbf_file, encoding='cp1251')
    for record_num, record in enumerate(table2, start=1):
        if record_num > 10:
            break
        name = str(record.get('NAME', '') or '').strip()
        print(f"   {record_num}. NAME: '{name}'")

# Проверяем что в базе Django
print("\n" + "═"*60)
print("ШАГ 3: Проверка импорта в Django")
print("═"*60)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import OeKod, Product, Brand

total_oe = OeKod.objects.count()
print(f"\nОЕ аналогов в базе: {total_oe:,}")

if found_records:
    print(f"\nПроверяем найденные записи в базе Django:")
    
    for i, rec in enumerate(found_records[:5], 1):
        print(f"\n{i}. Запись из файла:")
        print(f"   NAME: '{rec['name']}'")
        print(f"   ID_TOVAR: '{rec['id_tovar']}'")
        
        # Проверка 1: Есть ли товар?
        product = Product.objects.filter(tmp_id=rec['id_tovar']).first()
        if product:
            print(f"   ✅ Товар найден: {product.tmp_id} - {product.name[:50]}")
        else:
            print(f"   ❌ ТОВАР НЕ НАЙДЕН! ID_TOVAR={rec['id_tovar']}")
            print(f"      ПРИЧИНА ПРОПУСКА: Товар не импортирован!")
            
            # Попробуем без -dupN суффикса
            clean_id = rec['id_tovar'].split('-dup')[0]
            product_clean = Product.objects.filter(tmp_id=clean_id).first()
            if product_clean:
                print(f"      ℹ️ Найден товар без суффикса: {clean_id}")
            continue
        
        # Проверка 2: Есть ли бренд?
        if rec['id_brend']:
            brand = Brand.objects.filter(code=rec['id_brend']).first()
            if brand:
                print(f"   ✅ Бренд найден: {brand.name}")
            else:
                print(f"   ⚠️ Бренд не найден: {rec['id_brend']} (некритично)")
        
        # Проверка 3: Есть ли OE в базе?
        oe = OeKod.objects.filter(id_oe=rec['id_oe']).first()
        if oe:
            print(f"   ✅ OE импортирован в базу:")
            print(f"      oe_kod: '{oe.oe_kod}'")
            print(f"      oe_kod_clean: '{oe.oe_kod_clean}'")
        else:
            print(f"   ❌ OE НЕ импортирован! ID_oe={rec['id_oe']}")

# Финальная статистика
print("\n" + "═"*60)
print("📊 ИТОГОВАЯ СТАТИСТИКА:")
print("═"*60)

print(f"\nВ файле DBF:")
print(f"   Всего записей: {total_records:,}")
print(f"   С NAME='{search_name}': {len(found_records)}")

print(f"\nВ базе Django:")
print(f"   Всего OE: {total_oe:,}")
print(f"   Товаров: {Product.objects.count():,}")
print(f"   Брендов: {Brand.objects.count():,}")

# Проверяем лог последнего импорта
from shop.models import ImportFile

last_import = ImportFile.objects.filter(file_type='analogs').order_by('-created_at').first()
if last_import:
    print(f"\nПоследний импорт OE:")
    print(f"   Файл: {last_import.original_filename}")
    print(f"   Дата: {last_import.created_at}")
    print(f"   Статус: {last_import.status}")
    print(f"   Всего строк: {last_import.total_rows}")
    print(f"   Создано: {last_import.created_products}")
    print(f"   Обновлено: {last_import.updated_products}")
    print(f"   Ошибок: {last_import.error_count}")

print("\n" + "═"*60)
print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
print("═"*60)

