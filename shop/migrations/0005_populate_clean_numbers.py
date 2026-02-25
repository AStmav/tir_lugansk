# Generated migration for populating clean numbers

from django.db import migrations
import re


def populate_clean_numbers_forward(apps, schema_editor):
    """Заполняет очищенные номера для существующих товаров"""
    Product = apps.get_model('shop', 'Product')
    
    def clean_number(number):
        """Удаляет все символы кроме букв и цифр"""
        if not number:
            return ''
        return re.sub(r'[^a-zA-Z0-9]', '', str(number))
    
    print('🔄 Начинаем заполнение очищенных номеров...')
    
    products = Product.objects.all()
    total = products.count()
    
    if total == 0:
        print('ℹ️ Нет товаров для обработки')
        return
    
    print(f'📊 Всего товаров: {total}')
    
    batch = []
    updated_count = 0
    batch_size = 1000
    
    for product in products.iterator(chunk_size=batch_size):
        product.catalog_number_clean = clean_number(product.catalog_number)
        product.artikyl_number_clean = clean_number(product.artikyl_number)
        batch.append(product)
        
        if len(batch) >= batch_size:
            Product.objects.bulk_update(
                batch, 
                ['catalog_number_clean', 'artikyl_number_clean'],
                batch_size=batch_size
            )
            updated_count += len(batch)
            progress = (updated_count / total) * 100
            print(f'⏳ Прогресс: {progress:.1f}% ({updated_count}/{total})')
            batch = []
    
    # Сохраняем остатки
    if batch:
        Product.objects.bulk_update(
            batch, 
            ['catalog_number_clean', 'artikyl_number_clean'],
            batch_size=batch_size
        )
        updated_count += len(batch)
    
    print(f'✅ Готово! Обновлено {updated_count} товаров')


def populate_clean_numbers_reverse(apps, schema_editor):
    """Откат миграции - очищает поля"""
    Product = apps.get_model('shop', 'Product')
    Product.objects.all().update(
        catalog_number_clean='',
        artikyl_number_clean=''
    )


class Migration(migrations.Migration):
    
    dependencies = [
        ('shop', '0004_add_clean_fields_and_update_oekod'),  # Предыдущая миграция с добавлением полей
    ]
    
    operations = [
        migrations.RunPython(
            populate_clean_numbers_forward,
            reverse_code=populate_clean_numbers_reverse
        ),
    ]

