#!/usr/bin/env python3
"""
Скрипт для проверки чувствительности к регистру в базе данных
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
from django.db import connection

def check_case_sensitivity():
    """
    Проверяет чувствительность к регистру в базе данных
    """
    print("=" * 80)
    print("Проверка чувствительности к регистру")
    print("=" * 80)
    
    # Находим товары с "антискотч" в названии
    products = Product.objects.filter(name__icontains='Антискотч')
    print(f"\nПоиск 'Антискотч' (с большой буквы): {products.count()} товаров")
    for p in products:
        print(f"  - {p.name} (ID: {p.id})")
        print(f"    Название в БД: '{p.name}'")
        print(f"    Первая буква: '{p.name[0]}' (код: {ord(p.name[0])})")
    
    # Проверяем с маленькой буквы
    products_lower = Product.objects.filter(name__icontains='антискотч')
    print(f"\nПоиск 'антискотч' (с маленькой буквы): {products_lower.count()} товаров")
    
    # Проверяем напрямую через SQL
    print("\n" + "=" * 80)
    print("Проверка через SQL запросы:")
    print("=" * 80)
    
    with connection.cursor() as cursor:
        # Проверяем с LIKE (case-sensitive)
        cursor.execute("""
            SELECT id, name 
            FROM shop_product 
            WHERE name LIKE '%антискотч%' 
            LIMIT 5
        """)
        results_like = cursor.fetchall()
        print(f"\nSQL LIKE '%антискотч%' (case-sensitive): {len(results_like)} результатов")
        for row in results_like:
            print(f"  - ID: {row[0]}, Название: {row[1]}")
        
        # Проверяем с ILIKE (case-insensitive, PostgreSQL)
        cursor.execute("""
            SELECT id, name 
            FROM shop_product 
            WHERE name ILIKE '%антискотч%' 
            LIMIT 5
        """)
        results_ilike = cursor.fetchall()
        print(f"\nSQL ILIKE '%антискотч%' (case-insensitive): {len(results_ilike)} результатов")
        for row in results_ilike:
            print(f"  - ID: {row[0]}, Название: {row[1]}")
        
        # Проверяем с LOWER
        cursor.execute("""
            SELECT id, name 
            FROM shop_product 
            WHERE LOWER(name) LIKE LOWER('%антискотч%') 
            LIMIT 5
        """)
        results_lower = cursor.fetchall()
        print(f"\nSQL LOWER(name) LIKE LOWER('%антискотч%'): {len(results_lower)} результатов")
        for row in results_lower:
            print(f"  - ID: {row[0]}, Название: {row[1]}")
    
    # Проверяем, какая база данных используется
    print("\n" + "=" * 80)
    print("Информация о базе данных:")
    print("=" * 80)
    db_backend = connection.vendor
    print(f"База данных: {db_backend}")
    print(f"Версия: {connection.get_server_version()}")
    
    # Проверяем collation для таблицы
    if db_backend == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name, column_name, collation_name
                FROM information_schema.columns
                WHERE table_name = 'shop_product' 
                AND column_name = 'name'
            """)
            collation = cursor.fetchone()
            if collation:
                print(f"Collation для shop_product.name: {collation[2]}")
    
    # Проверяем, как Django генерирует SQL для icontains
    print("\n" + "=" * 80)
    print("SQL запрос, генерируемый Django для icontains:")
    print("=" * 80)
    query = Product.objects.filter(name__icontains='антискотч').query
    print(query)
    print(f"\nSQL: {query.sql}")
    if hasattr(query, 'params'):
        print(f"Параметры: {query.params}")

if __name__ == '__main__':
    check_case_sensitivity()

