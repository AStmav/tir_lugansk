import csv
import os
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.db import transaction, connection
from shop.models import Category, Brand, Product
from shop.models import ImportFile
from django.utils import timezone
import logging
from django.db.models import Q
from collections import defaultdict
import chardet

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Быстрый импорт товаров из CSV файла 1С (оптимизирован для больших файлов)'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV файлу')
        parser.add_argument('--batch-size', type=int, default=5000, help='Размер пачки для bulk_create (по умолчанию 5000)')
        parser.add_argument('--skip-rows', type=int, default=0, help='Пропустить N строк (для продолжения)')
        parser.add_argument('--delimiter', type=str, default='#', help='Разделитель в CSV файле')
        parser.add_argument('--encoding', type=str, default='auto', help='Кодировка файла (auto, utf-8, cp1251, windows-1251)')
        parser.add_argument('--disable-transactions', action='store_true', help='Отключить транзакции для ускорения')
        parser.add_argument('--import-file-id', type=int, default=None, help='ID записи ImportFile для обновления прогресса')
        parser.add_argument('--clear-existing', action='store_true', help='Очистить существующие товары перед импортом')
        parser.add_argument('--test-lines', type=int, default=0, help='Ограничить импорт первыми N строками (для тестирования)')

    def detect_encoding(self, file_path):
        """Автоматически определяет кодировку файла"""
        try:
            with open(file_path, 'rb') as file:
                raw_data = file.read(10000)  # Читаем первые 10KB для определения кодировки
                result = chardet.detect(raw_data)
                detected_encoding = result['encoding']
                confidence = result['confidence']
                
                self.stdout.write(f'Определена кодировка: {detected_encoding} (уверенность: {confidence:.2f})')
                
                # Популярные кодировки для русских файлов
                common_encodings = ['utf-8', 'cp1251', 'windows-1251', 'iso-8859-1']
                
                if detected_encoding and detected_encoding.lower() in common_encodings:
                    return detected_encoding
                else:
                    self.stdout.write('Пробуем популярные кодировки...')
                    return 'cp1251' 
                    
        except Exception as e:
            self.stdout.write(f'Ошибка определения кодировки: {e}')
            return 'cp1251'

    def try_read_file(self, file_path, encoding):
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                for i, line in enumerate(file):
                    if i >= 5: 
                        break
                return True
        except UnicodeDecodeError:
            return False
        except Exception:
            return False

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        batch_size = options['batch_size']
        skip_rows = options['skip_rows']
        delimiter = options['delimiter']
        encoding = options['encoding']
        disable_transactions = options['disable_transactions']
        import_file_id = options.get('import_file_id')
        clear_existing = options.get('clear_existing', False)
        test_lines = options.get('test_lines', 0)
        import_file = None
        
        if import_file_id:
            import_file = ImportFile.objects.filter(id=import_file_id).first()
            if import_file:
                # Сбрасываем старые ошибки/счётчики на старте
                ImportFile.objects.filter(id=import_file.id).update(
                    status='processing',
                    error_log='',
                    processed=False,
                    current_row=0,
                    processed_rows=0,
                    created_products=0,
                    updated_products=0,
                    error_count=0,
                )
        
        # Очищаем существующие товары если указан флаг
        if clear_existing:
            self.stdout.write('Очищаем существующие товары...')
            deleted_count = Product.objects.count()
            Product.objects.all().delete()
            self.stdout.write(f'Удалено {deleted_count} существующих товаров')
            logger.info(f"Удалено {deleted_count} существующих товаров")
            
            # Очищаем кэши
            existing_tmp_ids = set()
            existing_codes = set()
            all_categories = {}
            all_brands = {}
        else:
            # Загружаем существующие данные в память для быстрого поиска
            self.stdout.write('Загружаем существующие данные в память...')
            
            existing_tmp_ids = set(Product.objects.values_list('tmp_id', flat=True))
            existing_codes = set(Product.objects.values_list('slug', flat=True))
            all_categories = {cat.slug: cat for cat in Category.objects.all()}
            all_brands = {brand.slug: brand for brand in Brand.objects.all()}
            
            self.stdout.write(f'Загружено {len(existing_tmp_ids)} существующих товаров по TMP_ID')
            self.stdout.write(f'Загружено {len(existing_codes)} существующих товаров по коду')
            self.stdout.write(f'Загружено {len(all_categories)} существующих категорий')
            self.stdout.write(f'Загружено {len(all_brands)} существующих брендов')
            
            logger.info(f"Загружено {len(existing_tmp_ids)} существующих товаров по TMP_ID")
            logger.info(f"Загружено {len(existing_codes)} существующих товаров по коду")
            logger.info(f"Загружено {len(all_categories)} существующих категорий")
            logger.info(f"Загружено {len(all_brands)} существующих брендов")
        
        # Инициализируем кэши и счетчики
        categories_cache = {}
        brands_cache = {}
        created_categories = 0
        created_brands = 0
        created_products = 0
        updated_products = 0
        errors = 0
        processed_rows = 0
        
        logger.info(f"Начинаем импорт товаров из файла: {csv_file}")
        logger.info(f"Параметры: batch_size={batch_size}, skip_rows={skip_rows}, delimiter='{delimiter}', encoding={encoding}")
        
        if not os.path.exists(csv_file):
            error_msg = f'CSV файл не найден: {csv_file}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)
            return

        if encoding == 'auto':
            encoding = self.detect_encoding(csv_file)
        
        encodings_to_try = [encoding, 'cp1251', 'windows-1251', 'utf-8-sig', 'utf-8']
        
        working_encoding = None
        for enc in encodings_to_try:
            if self.try_read_file(csv_file, enc):
                working_encoding = enc
                self.stdout.write(f'Успешно открыт файл с кодировкой: {enc}')
                logger.info(f"Файл успешно открыт с кодировкой: {enc}")
                break
        
        if not working_encoding:
            error_msg = 'Не удалось открыть файл ни с одной кодировкой'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)
            return

        products_batch = []
        products_to_update = []
        
        stats = defaultdict(int)

        try:
            if not disable_transactions:
                connection.autocommit = False
            
            with open(csv_file, 'r', encoding=working_encoding) as file:
                # Определяем общее количество строк
                total_lines = sum(1 for _ in file)
                file.seek(0)
                
                self.stdout.write(f'Всего строк в файле: {total_lines}')
                if import_file:
                    ImportFile.objects.filter(id=import_file.id).update(total_rows=total_lines)
                
                reader = csv.DictReader(file, delimiter=delimiter)
                
                # Пропускаем уже обработанные строки
                for _ in range(skip_rows):
                    try:
                        next(reader)
                        processed_rows += 1
                    except StopIteration:
                        break
                
                self.stdout.write(f'Пропущено {skip_rows} строк, начинаем с строки {skip_rows + 1}')
                
                # Подсчитываем общее количество строк
                total_lines = sum(1 for _ in reader)
                self.stdout.write(f'Всего строк в файле: {total_lines}')
                logger.info(f"Всего строк в файле: {total_lines}")
                if import_file:
                    ImportFile.objects.filter(id=import_file.id).update(total_rows=total_lines)
                
                # Проверяем на дублирующиеся tmp_id
                file.seek(0)
                reader = csv.DictReader(file, delimiter=delimiter)
                tmp_ids_in_csv = set()
                duplicate_tmp_ids = set()
                
                for row in reader:
                    tmp_id = row.get('TMP_ID', '').strip()
                    if tmp_id:
                        if tmp_id in tmp_ids_in_csv:
                            duplicate_tmp_ids.add(tmp_id)
                        else:
                            tmp_ids_in_csv.add(tmp_id)
                
                if duplicate_tmp_ids:
                    self.stdout.write(self.style.WARNING(f'Найдено {len(duplicate_tmp_ids)} дублирующихся TMP_ID в CSV файле'))
                    logger.warning(f"Найдено {len(duplicate_tmp_ids)} дублирующихся TMP_ID в CSV файле")
                
                self.stdout.write(f'Уникальных TMP_ID в CSV: {len(tmp_ids_in_csv)}')
                logger.info(f"Уникальных TMP_ID в CSV: {len(tmp_ids_in_csv)}")
                
                # Возвращаемся в начало файла для основного импорта
                file.seek(0)
                reader = csv.DictReader(file, delimiter=delimiter)

                for row_num, row in enumerate(reader, start=skip_rows + 1):
                    try:
                        # Ограничиваем количество строк для тестирования
                        if test_lines > 0 and row_num > test_lines:
                            self.stdout.write(f'Достигнут лимит тестовых строк: {test_lines}')
                            break
                        
                        # Парсим данные по новой структуре
                        tmp_id = row.get('TMP_ID', '').strip()
                        name = row.get('NAME', '').strip()
                        producer_id = row.get('PROPERTY_PRODUCER_ID', '').strip()
                        tmc_number = row.get('PROPERTY_TMC_NUMBER', '').strip()
                        artikyl_number = row.get('PROPERTY_ARTIKYL_NUMBER', '').strip()
                        model_avto = row.get('PROPERTY_MODEL_AVTO', '').strip()
                        cross_number = row.get('PROPERTY_CROSS_NUMBER', '').strip()
                        section_id = row.get('SECTION_ID', '').strip()
                        
                        # Логируем первые несколько строк для отладки
                        if row_num <= 5:
                            logger.info(f"Строка {row_num}: TMP_ID={tmp_id}, NAME={name}, PRODUCER={producer_id}, SECTION={section_id}, APPLICABILITY={model_avto}")
                        
                        # Очищаем SECTION_ID от квадратных скобок и других символов
                        if section_id:
                            section_id = section_id.replace('[', '').replace(']', '').replace(';', '').strip()
                        
                        if not tmp_id or not name:
                            stats['skipped_empty'] += 1
                            continue
                        
                        # Проверяем, что у товара есть бренд и категория
                        if not producer_id:
                            logger.warning(f"Строка {row_num}: Товар {tmp_id} без производителя")
                        if not section_id:
                            logger.warning(f"Строка {row_num}: Товар {tmp_id} без категории")
                        
                        # Логируем каждые 1000 строк для отслеживания прогресса
                        if row_num % 1000 == 0:
                            logger.info(f"Обработано строк: {row_num}/{total_lines} ({(row_num/total_lines)*100:.1f}%)")
                            if import_file:
                                # Промежуточное обновление прогресса
                                ImportFile.objects.filter(id=import_file.id).update(
                                    current_row=row_num,
                                    processed_rows=processed_rows,
                                    created_products=stats['new_products'],
                                    error_count=errors,
                                )
                        
                        brand = None
                        if producer_id:
                            # Создаем slug из названия бренда, а не используем название как slug
                            brand_slug = slugify(producer_id)
                            if brand_slug in all_brands:
                                brand = all_brands[brand_slug]
                                logger.info(f"Найден существующий бренд: {brand.name} (slug: {brand_slug})")
                            elif brand_slug not in brands_cache:
                                brand, created = Brand.objects.get_or_create(
                                    slug=brand_slug,
                                    defaults={
                                        'name': producer_id,  # Сохраняем оригинальное название
                                        'description': f'Автоматически созданный бренд для {producer_id}'
                                    }
                                )
                                all_brands[brand_slug] = brand
                                brands_cache[brand_slug] = brand
                                if created:
                                    stats['new_brands'] += 1
                                    self.stdout.write(f'Создан бренд: {brand.name}')
                                    logger.info(f"Создан новый бренд: {brand.name} (slug: {brand_slug})")
                        else:
                            logger.warning(f"Строка {row_num}: Отсутствует производитель для товара {tmp_id}")
                        
                        # Создаем/получаем категорию (с кэшем)
                        category = None
                        if section_id:
                            # Создаем slug из SECTION_ID, а не используем SECTION_ID как slug
                            category_slug = slugify(section_id)
                            if category_slug in all_categories:
                                category = all_categories[category_slug]
                                logger.info(f"Найдена существующая категория: {category.name} (slug: {category_slug})")
                            elif category_slug not in categories_cache:
                                # Создаем категорию сразу
                                category, created = Category.objects.get_or_create(
                                    slug=category_slug,
                                    defaults={
                                        'name': f'Категория {section_id}',
                                        'description': f'Автоматически созданная категория для {section_id}'
                                    }
                                )
                                all_categories[category_slug] = category
                                categories_cache[category_slug] = category
                                if created:
                                    stats['new_categories'] += 1
                                    self.stdout.write(f'Создана категория: {category.name}')
                                    logger.info(f"Создана новая категория: {category.name} (slug: {category_slug})")
                        else:
                            logger.warning(f"Строка {row_num}: Отсутствует категория для товара {tmp_id}")
                        
                        base_slug = slugify(name)[:30]  
                        slug = f"{base_slug}-{tmp_id}"
                        
                        counter = 1
                        original_slug = slug
                        while slug in existing_codes:
                            slug = f"{original_slug}-{counter}"
                            counter += 1
                        
                        product = Product(
                            tmp_id=tmp_id,
                            name=name[:200], 
                            slug=slug,
                            category=category,
                            brand=brand,
                            code=tmc_number or tmp_id,
                            catalog_number=tmc_number or tmp_id,
                            cross_number=cross_number[:100] if cross_number else '',
                            artikyl_number=artikyl_number[:100] if artikyl_number else '',
                            applicability=model_avto[:500] if model_avto else 'Уточняйте',
                            price=0,
                            in_stock=True,
                            is_new=True,
                        )
                        
                        # Логируем создание товара для отладки
                        if row_num <= 5:
                            logger.info(f"Создается товар: {product.name}, бренд: {product.brand.name if product.brand else 'Нет'}, категория: {product.category.name if product.category else 'Нет'}")
                        
                        products_batch.append(product)
                        stats['new_products'] += 1
                        processed_rows += 1
                        
                        if stats['new_products'] % 100 == 0:
                            logger.info(f"Создано товаров: {stats['new_products']}, обработано строк: {processed_rows}")
                        
                        if processed_rows % 1000 == 0:
                            progress = (processed_rows / total_lines) * 100
                            self.stdout.write(f'Прогресс: {progress:.1f}% ({processed_rows}/{total_lines}) | Создано товаров: {stats["new_products"]}')
                            if import_file:
                                ImportFile.objects.filter(id=import_file.id).update(
                                    current_row=processed_rows,
                                    processed_rows=processed_rows,
                                    created_products=stats['new_products'],
                                    error_count=errors,
                                )
                        
                        if len(products_batch) >= batch_size:
                            self._save_products_batch(products_batch)
                            logger.info(f"Сохранена пачка товаров: {len(products_batch)}")
                            products_batch = []
                            if import_file:
                                ImportFile.objects.filter(id=import_file.id).update(
                                    processed_rows=processed_rows,
                                    created_products=stats['new_products']
                                )
                            
                    except Exception as e:
                        errors += 1
                        if errors <= 10:  
                            error_msg = f'Ошибка в строке {row_num}: {str(e)}'
                            self.stdout.write(self.style.ERROR(error_msg))
                            logger.error(f"Ошибка в строке {row_num}: {str(e)}")
                        if import_file:
                            ImportFile.objects.filter(id=import_file.id).update(error_count=errors)
                        continue
                
                if products_batch:
                    self._save_products_batch(products_batch)
                    logger.info(f"Сохранена финальная пачка товаров: {len(products_batch)}")
                
                if not disable_transactions:
                    connection.autocommit = True
                
                final_stats = (
                    f'\nИмпорт завершен!\n'
                    f'Обработано строк: {processed_rows}\n'
                    f'Создано категорий: {stats["new_categories"]}\n'
                    f'Создано брендов: {stats["new_brands"]}\n'
                    f'Создано товаров: {stats["new_products"]}\n'
                    f'Пропущено пустых строк: {stats["skipped_empty"]}\n'
                    f'Существующих товаров: {stats["existing_products"]}\n'
                    f'Ошибок: {errors}'
                )
                
                self.stdout.write(self.style.SUCCESS(final_stats))
                logger.info(f"Импорт завершен успешно: {final_stats}")
                if import_file:
                    ImportFile.objects.filter(id=import_file.id).update(
                        processed=True,
                        processed_at=timezone.now(),
                        status='completed',
                        current_row=processed_rows,
                        processed_rows=processed_rows,
                        created_products=stats['new_products'],
                        error_count=errors,
                    )
                
        except Exception as e:
            error_msg = f'Критическая ошибка: {str(e)}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(f'Критическая ошибка импорта: {str(e)}')
            if not disable_transactions:
                connection.autocommit = True
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)

    def _save_products_batch(self, products_batch):
        try:
            logger.info(f"Попытка сохранения пачки из {len(products_batch)} товаров")
            
            created_products = Product.objects.bulk_create(products_batch, ignore_conflicts=True)
            
            actual_count = len(created_products)
            logger.info(f"Фактически создано товаров: {actual_count} из {len(products_batch)}")
            
            if actual_count < len(products_batch):
                logger.warning(f"Пропущено товаров из-за конфликтов: {len(products_batch) - actual_count}")
            
            self.stdout.write(f'Сохранена пачка из {len(products_batch)} товаров')
            logger.info(f"Успешно сохранена пачка из {len(products_batch)} товаров")
            
        except Exception as e:
            error_msg = f'Ошибка сохранения пачки товаров: {str(e)}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(f"Ошибка сохранения пачки товаров: {str(e)}")
            for product in products_batch:
                try:
                    product.save()
                    logger.info(f"Товар {product.tmp_id} сохранен по одному")
                except Exception as single_error:
                    logger.error(f"Не удалось сохранить товар {product.tmp_id}: {str(single_error)}") 