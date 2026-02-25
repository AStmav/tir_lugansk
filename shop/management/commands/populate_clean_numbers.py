"""
Команда для заполнения очищенных номеров у существующих товаров
Запуск: python manage.py populate_clean_numbers
"""
from django.core.management.base import BaseCommand
from shop.models import Product
import re


class Command(BaseCommand):
    help = 'Заполняет очищенные номера (catalog_number_clean, artikyl_number_clean) для существующих товаров'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Размер пачки для обновления (по умолчанию 1000)'
        )
    
    def handle(self, *args, **options):
        batch_size = options['batch_size']
        
        self.stdout.write('🔄 Начинаем заполнение очищенных номеров...')
        
        # Получаем все товары
        products = Product.objects.all()
        total = products.count()
        
        self.stdout.write(f'📊 Всего товаров: {total}')
        
        updated_count = 0
        batch = []
        
        for i, product in enumerate(products, 1):
            # Очищаем номера
            product.catalog_number_clean = Product.clean_number(product.catalog_number)
            product.artikyl_number_clean = Product.clean_number(product.artikyl_number)
            
            batch.append(product)
            
            # Сохраняем пачку
            if len(batch) >= batch_size:
                Product.objects.bulk_update(
                    batch, 
                    ['catalog_number_clean', 'artikyl_number_clean']
                )
                updated_count += len(batch)
                progress = (updated_count / total) * 100
                self.stdout.write(f'⏳ Прогресс: {progress:.1f}% ({updated_count}/{total})')
                batch = []
        
        # Сохраняем остатки
        if batch:
            Product.objects.bulk_update(
                batch, 
                ['catalog_number_clean', 'artikyl_number_clean']
            )
            updated_count += len(batch)
        
        self.stdout.write(self.style.SUCCESS(f'✅ Готово! Обновлено {updated_count} товаров'))
        
        # Показываем примеры
        self.stdout.write('\n📋 Примеры очищенных номеров:')
        sample_products = Product.objects.filter(
            catalog_number_clean__isnull=False
        ).exclude(catalog_number_clean='')[:5]
        
        for product in sample_products:
            self.stdout.write(f'   "{product.catalog_number}" → "{product.catalog_number_clean}"')

