import csv
import os
import time
import hashlib
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction, OperationalError
from django.utils.text import slugify
from shop.models import Product, Category, Brand, ImportFile, OeKod


class Command(BaseCommand):
    help = 'Импорт товаров из CSV файла 1С'
    
    def add_arguments(self, parser):
        parser.add_argument('--file-id', type=int, help='ID файла импорта')
        parser.add_argument('--csv-path', type=str, help='Путь к CSV файлу')
    
    def handle(self, *args, **options):
        file_id = options.get('file_id')
        csv_path = options.get('csv_path')
        
        if file_id:
            try:
                import_file = ImportFile.objects.get(id=file_id)
                csv_path = import_file.file.path
            except ImportFile.DoesNotExist:
                raise CommandError(f'Файл импорта с ID {file_id} не найден')
        elif not csv_path:
            raise CommandError('Укажите --file-id или --csv-path')
        
        self.stdout.write(f'Начинаем импорт из файла: {csv_path}')
        
        try:
            result = self.import_csv(csv_path, import_file if file_id else None)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Импорт завершен успешно!\n'
                    f'Обработано строк: {result["processed_rows"]}\n'
                    f'Создано товаров: {result["created_products"]}\n'
                    f'Обновлено товаров: {result["updated_products"]}'
                )
            )
        except Exception as e:
            if file_id:
                import_file.status = 'failed'
                import_file.error_log = str(e)
                import_file.save()
            raise CommandError(f'Ошибка импорта: {str(e)}')
    
    def check_cancellation(self, import_file):
        """Проверяет был ли отменен импорт"""
        if import_file:
            # Обновляем данные из БД
            import_file.refresh_from_db()
            if import_file.cancelled:
                self.stdout.write(self.style.WARNING('Импорт отменен пользователем'))
                import_file.status = 'cancelled'
                import_file.save()
                return True
        return False
    
    def import_csv(self, csv_path, import_file=None):
        """Основная логика импорта CSV"""
        processed_rows = 0
        created_products = 0
        updated_products = 0
        total_rows = 0
        error_log = []
        error_count = 0
        
        # Обновляем статус начала импорта
        if import_file:
            import_file.status = 'processing'
            import_file.save()
        
        # Читаем CSV файл
        with open(csv_path, 'r', encoding='utf-8-sig') as file:
            # Подсчитываем общее количество строк
            total_rows = sum(1 for line in file) - 1  # -1 для заголовка
            file.seek(0)
            
            # Обновляем общее количество строк
            if import_file:
                import_file.total_rows = total_rows
                import_file.save()
            
            reader = csv.DictReader(file, delimiter=';')
            
            # УСКОРЕНИЕ: Обрабатываем по большим пакетам для максимальной производительности
            batch_size = 5000  # Увеличили в 100 раз!
            batch_rows = []
            
            for row_num, row in enumerate(reader, 1):
                # Проверяем отмену импорта только изредка для скорости
                if row_num % 1000 == 0 and self.check_cancellation(import_file):
                    break
                
                batch_rows.append((row_num, row))
                
                # Обрабатываем пакет
                if len(batch_rows) >= batch_size:
                    result = self.process_batch(batch_rows, import_file)
                    processed_rows += result['processed']
                    created_products += result['created']
                    updated_products += result['updated']
                    error_count += result['errors']
                    error_log.extend(result['error_log'])
                    
                    # УСКОРЕНИЕ: Обновляем прогресс только каждые 1000 строк вместо каждых 10
                    if import_file:
                        import_file.current_row = row_num
                        import_file.processed_rows = processed_rows
                        import_file.created_products = created_products
                        import_file.updated_products = updated_products
                        import_file.error_count = error_count
                        import_file.save(update_fields=[
                            'current_row', 'processed_rows', 'created_products', 
                            'updated_products', 'error_count'
                        ])
                    
                    self.stdout.write(f'Обработано {processed_rows}/{total_rows} строк...')
                    batch_rows = []
            
            # Обрабатываем оставшиеся строки
            if batch_rows and not self.check_cancellation(import_file):
                result = self.process_batch(batch_rows, import_file)
                processed_rows += result['processed']
                created_products += result['created']
                updated_products += result['updated']
                error_count += result['errors']
                error_log.extend(result['error_log'])
        
        # Финальное обновление статистики импорта
        if import_file:
            if import_file.cancelled:
                import_file.status = 'cancelled'
            else:
                import_file.status = 'completed' if error_count == 0 else 'completed'
                import_file.processed = True
                import_file.processed_at = timezone.now()
            
            import_file.current_row = total_rows
            import_file.total_rows = total_rows
            import_file.processed_rows = processed_rows
            import_file.created_products = created_products
            import_file.updated_products = updated_products
            import_file.error_count = error_count
            import_file.error_log = '\n'.join(error_log)
            import_file.save()
        
        return {
            'processed_rows': processed_rows,
            'created_products': created_products,
            'updated_products': updated_products,
            'total_rows': total_rows,
            'error_count': error_count
        }
    
    def process_batch(self, batch_rows, import_file):
        """Обработка пакета строк с повторными попытками при блокировке БД"""
        processed = 0
        created = 0
        updated = 0
        errors = 0
        error_log = []
        
        max_retries = 3
        retry_delay = 0.5  # Уменьшили задержку для скорости
        
        for attempt in range(max_retries):
            try:
                # УСКОРЕНИЕ: Используем bulk операции Django для максимальной скорости
                products_to_create = []
                products_to_update = []
                
                with transaction.atomic():
                    for row_num, row in batch_rows:
                        # Быстрая проверка отмены только каждые 500 строк в батче
                        if len(batch_rows) > 500 and (row_num % 500 == 0) and self.check_cancellation(import_file):
                            return {
                                'processed': processed,
                                'created': created,
                                'updated': updated,
                                'errors': errors,
                                'error_log': error_log
                            }
                        
                        try:
                            # УСКОРЕНИЕ: Минимальная обработка строки
                            result = self.process_row_fast(row)
                            if result['action'] == 'create':
                                products_to_create.append(result['product'])
                                created += 1
                            elif result['action'] == 'update':
                                products_to_update.append(result['product'])
                                updated += 1
                            processed += 1
                        except Exception as e:
                            errors += 1
                            error_msg = f'Строка {row_num}: {str(e)}'
                            error_log.append(error_msg)
                    
                    # УСКОРЕНИЕ: Bulk создание и обновление
                    if products_to_create:
                        Product.objects.bulk_create(products_to_create, ignore_conflicts=True)
                    
                    if products_to_update:
                        Product.objects.bulk_update(products_to_update, [
                            'name', 'category', 'brand', 'catalog_number', 'artikyl_number', 
                            'cross_number', 'applicability', 'price'
                        ])
                
                # Если дошли сюда, то транзакция прошла успешно
                break
                
            except OperationalError as e:
                if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f'База данных заблокирована, повторная попытка {attempt + 1}/{max_retries} через {retry_delay} сек...'
                        )
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Меньшее увеличение задержки
                else:
                    # Последняя попытка или другая ошибка
                    raise
        
        return {
            'processed': processed,
            'created': created,
            'updated': updated,
            'errors': errors,
            'error_log': error_log
        }
    
    def process_row_fast(self, row):
        """УСКОРЕННАЯ обработка одной строки CSV"""
        # Обязательные поля
        tmp_id = row.get('TMP_ID', '').strip()
        name = row.get('NAME', '').strip()
        
        if not tmp_id or not name:
            raise ValueError('Отсутствуют обязательные поля TMP_ID или NAME')
        
        # УСКОРЕНИЕ: Кешируем бренды и категории для избежания частых запросов к БД
        brand_name = row.get('PROPERTY_PRODUCER_ID', '').strip() or 'Неизвестный'
        brand = self.get_or_create_brand_cached(brand_name)
        
        section_id = row.get('SECTION_ID', '').strip()
        category = self.get_or_create_category_cached(section_id)
        
        # Данные товара
        catalog_number = row.get('PROPERTY_TMC_NUMBER', '').strip()
        artikyl_number = row.get('PROPERTY_ARTIKYL_NUMBER', '').strip()
        cross_number = row.get('PROPERTY_CROSS_NUMBER', '').strip()
        applicability = row.get('PROPERTY_MODEL_AVTO', '').strip()
        
        # Цена
        price_str = row.get('PRICE', '0').strip().replace(',', '.')
        try:
            price = Decimal(price_str) if price_str else Decimal('0')
        except InvalidOperation:
            price = Decimal('0')
        
        # Создание slug
        slug = slugify(f"{name}-{catalog_number}")
        if not slug:
            slug = f"product-{tmp_id}"
        
        # УСКОРЕНИЕ: Проверяем существование товара
        try:
            product = Product.objects.get(code=tmp_id)
            # Обновляем существующий товар
            product.name = name
            product.category = category
            product.brand = brand
            product.catalog_number = catalog_number
            product.artikyl_number = artikyl_number
            product.cross_number = cross_number
            product.applicability = applicability
            product.price = price
            
            return {'action': 'update', 'product': product}
        
        except Product.DoesNotExist:
            # Создаем новый товар
            product = Product(
                name=name,
                slug=self.generate_unique_slug(slug),
                code=tmp_id,
                category=category,
                brand=brand,
                catalog_number=catalog_number,
                artikyl_number=artikyl_number,
                cross_number=cross_number,
                applicability=applicability,
                price=price,
                in_stock=True
            )
            
            return {'action': 'create', 'product': product}
    
    # УСКОРЕНИЕ: Кеширование для брендов и категорий
    _brand_cache = {}
    _category_cache = {}
    
    def get_or_create_brand_cached(self, brand_name):
        """Кешированное получение/создание бренда"""
        if brand_name not in self._brand_cache:
            brand, created = Brand.objects.get_or_create(
                name=brand_name,
                defaults={'slug': slugify(brand_name) or 'unknown'}
            )
            self._brand_cache[brand_name] = brand
        return self._brand_cache[brand_name]
    
    def get_or_create_category_cached(self, section_id):
        """Кешированное получение/создание категории"""
        if not section_id:
            section_id = 'uncategorized'
        
        if section_id not in self._category_cache:
            if section_id == 'uncategorized':
                category, created = Category.objects.get_or_create(
                    slug='uncategorized',
                    defaults={
                        'name': 'Без категории',
                        'is_active': True
                    }
                )
            else:
                section_slug = section_id.lstrip('0') or 'cat-' + section_id
                category_slug = f'category-{section_slug}'
                
                category, created = Category.objects.get_or_create(
                    slug=category_slug,
                    defaults={
                        'name': f'Категория {section_id}',
                        'is_active': True
                    }
                )
            self._category_cache[section_id] = category
        return self._category_cache[section_id]
    
    def generate_unique_slug(self, base_slug):
        """Генерирует уникальный slug"""
        slug = base_slug
        counter = 1
        
        while Product.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug 