import csv
import os
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.db import transaction
from shop.models import Category, Brand, Product


class Command(BaseCommand):
    help = 'Импорт товаров из CSV файла 1С'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV файлу')
        parser.add_argument('images_folder', type=str, help='Путь к папке с изображениями')
        parser.add_argument('--batch-size', type=int, default=1000, help='Размер пачки для bulk_create')
        parser.add_argument('--skip-rows', type=int, default=0, help='Пропустить N строк (для продолжения)')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        images_folder = options['images_folder']
        batch_size = options['batch_size']
        skip_rows = options['skip_rows']
        
        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f'CSV файл не найден: {csv_file}'))
            return
            
        if not os.path.exists(images_folder):
            self.stdout.write(self.style.ERROR(f'Папка с изображениями не найдена: {images_folder}'))
            return

        # Счетчики
        created_categories = 0
        created_brands = 0
        created_products = 0
        errors = 0
        processed_rows = 0

        # Кэш для категорий и брендов
        categories_cache = {}
        brands_cache = {}
        
        # Получаем существующие товары для проверки дубликатов
        existing_codes = set(Product.objects.values_list('code', flat=True))
        self.stdout.write(f'Загружено {len(existing_codes)} существующих товаров')

        # Пачка товаров для bulk_create
        products_batch = []

        with open(csv_file, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file, delimiter=';')
            
            # Пропускаем уже обработанные строки
            for _ in range(skip_rows):
                try:
                    next(reader)
                    processed_rows += 1
                except StopIteration:
                    break
            
            self.stdout.write(f'Пропущено {skip_rows} строк, начинаем с строки {skip_rows + 1}')
            
            for row_num, row in enumerate(reader, start=skip_rows + 1):
                try:
                    # Парсим данные
                    tmp_id = row.get('TMP_ID', '').strip()
                    name = row.get('NAME', '').strip()
                    producer = row.get('PROPERTY_PRODUCER_ID', '').strip()
                    tmc_number = row.get('PROPERTY_TMC_NUMBER', '').strip()
                    model_avto = row.get('PROPERTY_MODEL_AVTO', '').strip()
                    section_id = row.get('SECTION_ID', '').strip()
                    
                    # Очищаем SECTION_ID от квадратных скобок
                    if section_id:
                        section_id = section_id.replace('[', '').replace(']', '').replace(';', '')
                    
                    if not tmp_id or not name:
                        continue
                    
                    # Проверяем существование товара
                    if tmp_id in existing_codes:
                        continue
                    
                    # Создаем/получаем категорию (с кэшем)
                    category = None
                    if section_id:
                        if section_id not in categories_cache:
                            category, created = Category.objects.get_or_create(
                                slug=f'category-{section_id}',
                                defaults={'name': f'Категория {section_id}'}
                            )
                            categories_cache[section_id] = category
                            if created:
                                created_categories += 1
                        else:
                            category = categories_cache[section_id]
                    
                    # Создаем/получаем бренд (с кэшем)
                    brand = None
                    if producer:
                        producer_slug = slugify(producer)
                        if producer_slug not in brands_cache:
                            brand, created = Brand.objects.get_or_create(
                                slug=producer_slug,
                                defaults={'name': producer}
                            )
                            brands_cache[producer_slug] = brand
                            if created:
                                created_brands += 1
                        else:
                            brand = brands_cache[producer_slug]
                    
                    # Добавляем товар в пачку
                    product = Product(
                        name=name,
                        slug=f'product-{tmp_id}',
                        category=category,
                        brand=brand,
                        code=tmp_id,
                        catalog_number=tmc_number,
                        applicability=model_avto,
                        price=0,
                        in_stock=True,
                    )
                    products_batch.append(product)
                    existing_codes.add(tmp_id)  # Добавляем в кэш для избежания дубликатов
                    
                    # Bulk create каждые batch_size товаров
                    if len(products_batch) >= batch_size:
                        with transaction.atomic():
                            Product.objects.bulk_create(products_batch, ignore_conflicts=True)
                        created_products += len(products_batch)
                        self.stdout.write(f'Обработано {created_products} товаров... (строка {row_num})')
                        products_batch = []
                    
                except Exception as e:
                    errors += 1
                    if errors % 100 == 0:
                        self.stdout.write(f'Ошибок: {errors}')
                
                processed_rows += 1
                
        # Сохраняем оставшиеся товары
        if products_batch:
            with transaction.atomic():
                Product.objects.bulk_create(products_batch, ignore_conflicts=True)
            created_products += len(products_batch)
        
        # Статистика
        self.stdout.write(self.style.SUCCESS('=== ИМПОРТ ЗАВЕРШЕН ==='))
        self.stdout.write(f'Обработано строк: {processed_rows}')
        self.stdout.write(f'Создано категорий: {created_categories}')
        self.stdout.write(f'Создано брендов: {created_brands}')
        self.stdout.write(f'Создано товаров: {created_products}')
        self.stdout.write(f'Ошибок: {errors}')
        
        if processed_rows > 0:
            self.stdout.write(f'\nДля продолжения с этого места используйте: --skip-rows {processed_rows}') 