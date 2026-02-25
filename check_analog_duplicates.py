#!/usr/bin/env python3
"""
Скрипт для проверки дубликатов аналогов у товара
"""
import os
import sys
import django

# Настройка Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import Product, OeKod
from django.db.models import Count

def check_analog_duplicates(tmp_id=None):
    """
    Проверяет дубликаты аналогов для товара
    """
    if tmp_id:
        try:
            product = Product.objects.get(tmp_id=tmp_id)
        except Product.DoesNotExist:
            print(f"Товар с tmp_id={tmp_id} не найден")
            return
    else:
        # Берем товар с максимальным количеством аналогов
        product = Product.objects.annotate(
            analog_count=Count('oe_analogs')
        ).order_by('-analog_count').first()
    
    if not product:
        print("Товары не найдены")
        return
    
    print(f"=" * 80)
    print(f"Товар: {product.name}")
    print(f"TMP_ID: {product.tmp_id}")
    print(f"ID: {product.id}")
    print(f"=" * 80)
    
    # Получаем все аналоги товара
    analogs = OeKod.objects.filter(product=product).select_related('brand')
    total_analogs = analogs.count()
    
    print(f"\nВсего аналогов: {total_analogs:,}")
    
    # Проверяем дубликаты по id_oe
    id_oe_counts = analogs.values('id_oe').annotate(
        count=Count('id_oe')
    ).filter(count__gt=1).order_by('-count')
    
    if id_oe_counts.exists():
        print(f"\n⚠️  НАЙДЕНЫ ДУБЛИКАТЫ по id_oe:")
        print(f"Количество дублирующихся id_oe: {id_oe_counts.count()}")
        for dup in id_oe_counts[:10]:
            print(f"  id_oe={dup['id_oe']}: {dup['count']} записей")
            # Показываем детали
            dup_analogs = analogs.filter(id_oe=dup['id_oe'])
            for a in dup_analogs:
                print(f"    - ID={a.id}, oe_kod={a.oe_kod}, brand={a.brand.name if a.brand else 'None'}")
    else:
        print(f"\n✓ Дубликатов по id_oe не найдено")
    
    # Проверяем дубликаты по oe_kod
    oe_kod_counts = analogs.values('oe_kod').annotate(
        count=Count('oe_kod')
    ).filter(count__gt=1).order_by('-count')
    
    if oe_kod_counts.exists():
        print(f"\n⚠️  НАЙДЕНЫ ДУБЛИКАТЫ по oe_kod:")
        print(f"Количество дублирующихся oe_kod: {oe_kod_counts.count()}")
        for dup in oe_kod_counts[:10]:
            print(f"  oe_kod={dup['oe_kod']}: {dup['count']} записей")
            # Показываем детали
            dup_analogs = analogs.filter(oe_kod=dup['oe_kod'])
            for a in dup_analogs:
                print(f"    - ID={a.id}, id_oe={a.id_oe}, brand={a.brand.name if a.brand else 'None'}")
    else:
        print(f"\n✓ Дубликатов по oe_kod не найдено")
    
    # Проверяем дубликаты по oe_kod_clean
    oe_kod_clean_counts = analogs.values('oe_kod_clean').annotate(
        count=Count('oe_kod_clean')
    ).filter(count__gt=1).order_by('-count')
    
    if oe_kod_clean_counts.exists():
        print(f"\n⚠️  НАЙДЕНЫ ДУБЛИКАТЫ по oe_kod_clean:")
        print(f"Количество дублирующихся oe_kod_clean: {oe_kod_clean_counts.count()}")
        for dup in oe_kod_clean_counts[:10]:
            print(f"  oe_kod_clean={dup['oe_kod_clean']}: {dup['count']} записей")
            # Показываем детали
            dup_analogs = analogs.filter(oe_kod_clean=dup['oe_kod_clean'])
            for a in dup_analogs:
                print(f"    - ID={a.id}, id_oe={a.id_oe}, oe_kod={a.oe_kod}, brand={a.brand.name if a.brand else 'None'}")
    else:
        print(f"\n✓ Дубликатов по oe_kod_clean не найдено")
    
    # Проверяем уникальность комбинации (id_oe, product)
    combo_counts = analogs.values('id_oe', 'product').annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    if combo_counts.exists():
        print(f"\n⚠️  НАЙДЕНЫ ДУБЛИКАТЫ по комбинации (id_oe, product):")
        print(f"Количество дублирующихся комбинаций: {combo_counts.count()}")
        for dup in combo_counts[:10]:
            print(f"  id_oe={dup['id_oe']}, product_id={dup['product']}: {dup['count']} записей")
    else:
        print(f"\n✓ Дубликатов по комбинации (id_oe, product) не найдено")
    
    # Статистика по уникальным значениям
    unique_id_oe = analogs.values('id_oe').distinct().count()
    unique_oe_kod = analogs.values('oe_kod').distinct().count()
    unique_oe_kod_clean = analogs.values('oe_kod_clean').distinct().count()
    
    print(f"\n" + "=" * 80)
    print(f"СТАТИСТИКА:")
    print(f"  Всего записей: {total_analogs:,}")
    print(f"  Уникальных id_oe: {unique_id_oe:,}")
    print(f"  Уникальных oe_kod: {unique_oe_kod:,}")
    print(f"  Уникальных oe_kod_clean: {unique_oe_kod_clean:,}")
    
    if total_analogs != unique_id_oe:
        print(f"\n⚠️  ВНИМАНИЕ: Количество записей ({total_analogs:,}) не совпадает с уникальными id_oe ({unique_id_oe:,})")
        print(f"  Разница: {total_analogs - unique_id_oe:,} дубликатов")
    else:
        print(f"\n✓ Все записи уникальны по id_oe")

if __name__ == '__main__':
    # Можно передать tmp_id как аргумент
    tmp_id = sys.argv[1] if len(sys.argv) > 1 else None
    if tmp_id:
        check_analog_duplicates(tmp_id=tmp_id)
    else:
        # Проверяем товар из логов
        check_analog_duplicates(tmp_id='000152917')

