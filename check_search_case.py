#!/usr/bin/env python3
"""
Скрипт для проверки поиска товаров с учетом регистра
"""
import os
import sys
import django

# Настройка Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tir_lugansk.settings')
django.setup()

from shop.models import Product
from django.db.models import Q

def check_search_case(search_term):
    """
    Проверяет поиск с разными регистрами
    """
    print(f"=" * 80)
    print(f"Проверка поиска для: '{search_term}'")
    print(f"=" * 80)
    
    # Проверяем, является ли это поиском по номеру
    from shop.models import OeKod
    is_number = OeKod.is_number_search(search_term)
    print(f"Определено как поиск по номеру: {is_number}")
    
    if is_number:
        print("\n⚠️  Это поиск по номеру, а не по тексту!")
        print("Текстовый поиск не будет выполнен.")
        return
    
    # Текстовый поиск
    base_queryset = Product.objects.filter(in_stock=True)
    
    text_search_query = (
        Q(name__icontains=search_term) |
        Q(brand__name__icontains=search_term) |
        Q(description__icontains=search_term) |
        Q(applicability__icontains=search_term)
    )
    
    results = base_queryset.filter(text_search_query)
    
    print(f"\nРезультаты поиска:")
    print(f"  Найдено товаров: {results.count()}")
    
    if results.exists():
        print(f"\nПервые 10 результатов:")
        for product in results[:10]:
            print(f"  - {product.name} (Бренд: {product.brand.name})")
            # Проверяем, где найдено совпадение
            if search_term.lower() in product.name.lower():
                print(f"    ✓ Найдено в названии")
            if search_term.lower() in product.brand.name.lower():
                print(f"    ✓ Найдено в бренде")
    else:
        print("\n⚠️  Товары не найдены!")
        
        # Проверяем, есть ли товары с похожими названиями
        print("\nПоиск похожих товаров (без учета регистра):")
        similar = base_queryset.filter(
            Q(name__icontains=search_term.lower()) |
            Q(name__icontains=search_term.capitalize()) |
            Q(name__icontains=search_term.upper())
        )
        print(f"  Найдено: {similar.count()}")
        if similar.exists():
            for product in similar[:5]:
                print(f"  - {product.name} (Бренд: {product.brand.name})")

if __name__ == '__main__':
    # Проверяем оба варианта
    check_search_case('антискотч')
    print("\n" + "=" * 80 + "\n")
    check_search_case('Антискотч')
    
    # Также проверим, есть ли такие товары в базе
    print("\n" + "=" * 80)
    print("Проверка наличия товаров с 'антискотч' в названии:")
    print("=" * 80)
    products = Product.objects.filter(
        name__icontains='антискотч'
    )
    print(f"Найдено товаров (без учета регистра): {products.count()}")
    if products.exists():
        for p in products[:10]:
            print(f"  - {p.name} (ID: {p.id}, TMP_ID: {p.tmp_id})")

