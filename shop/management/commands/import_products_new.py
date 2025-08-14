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
import re

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

    def parse_csv_line(self, line, delimiter='#'):
        """Парсит строку CSV с учетом специфики формата 1С"""
        # Удаляем лишние разделители в конце
        line = line.rstrip(delimiter).strip()
        # Разбиваем по разделителю
        fields = line.split(delimiter)
        
        # Убеждаемся, что у нас есть все нужные поля (8 полей)
        while len(fields) < 8:
            fields.append('')
            
        return {
            'TMP_ID': fields[0].strip() if len(fields) > 0 else '',
            'NAME': fields[1].strip() if len(fields) > 1 else '',
            'PROPERTY_PRODUCER_ID': fields[2].strip() if len(fields) > 2 else '',
            'PROPERTY_TMC_NUMBER': fields[3].strip() if len(fields) > 3 else '',
            'PROPERTY_ARTIKYL_NUMBER': fields[4].strip() if len(fields) > 4 else '',
            'PROPERTY_MODEL_AVTO': fields[5].strip() if len(fields) > 5 else '',
            'PROPERTY_CROSS_NUMBER': fields[6].strip() if len(fields) > 6 else '',
            'SECTION_ID': fields[7].strip() if len(fields) > 7 else '',
        }

    def count_lines_in_file(self, file_path, encoding, delimiter='#'):
        """Подсчитывает количество строк в CSV файле, исключая заголовок"""
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                lines = file.readlines()
                # Исключаем заголовок (первую строку)
                return len(lines) - 1 if len(lines) > 0 else 0
        except Exception as e:
            logger.error(f"Ошибка подсчета строк в файле: {e}")
            return 0

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

        # Подсчитываем общее количество строк
        total_lines = self.count_lines_in_file(csv_file, working_encoding, delimiter)
        self.stdout.write(f'Всего строк в файле (без заголовка): {total_lines}')
        logger.info(f"Всего строк в файле: {total_lines}")
        if import_file:
            ImportFile.objects.filter(id=import_file.id).update(total_rows=total_lines)

        products_batch = []
        products_to_update = []
        
        stats = defaultdict(int)

        try:
            if not disable_transactions:
                connection.autocommit = False
            
            with open(csv_file, 'r', encoding=working_encoding) as file:
                lines = file.readlines()
                
                # Пропускаем заголовок (первую строку)
                if len(lines) == 0:
                    self.stdout.write(self.style.ERROR('Файл пустой'))
                    return
                
                header_line = lines[0].strip()
                self.stdout.write(f'Заголовок: {header_line}')
                logger.info(f"Заголовок CSV: {header_line}")
                
                # Проверяем на дублирующиеся tmp_id
                tmp_ids_in_csv = set()
                duplicate_tmp_ids = set()
                
                for line_num, line in enumerate(lines[1:], start=1):  # Пропускаем заголовок
                    try:
                        row = self.parse_csv_line(line, delimiter)
                    tmp_id = row.get('TMP_ID', '').strip()
                    if tmp_id:
                        if tmp_id in tmp_ids_in_csv:
                            duplicate_tmp_ids.add(tmp_id)
                        else:
                            tmp_ids_in_csv.add(tmp_id)
                    except Exception as e:
                        logger.warning(f"Ошибка парсинга строки {line_num} при проверке дубликатов: {e}")
                        continue
                
                if duplicate_tmp_ids:
                    self.stdout.write(self.style.WARNING(f'Найдено {len(duplicate_tmp_ids)} дублирующихся TMP_ID в CSV файле'))
                    logger.warning(f"Найдено {len(duplicate_tmp_ids)} дублирующихся TMP_ID в CSV файле")
                
                self.stdout.write(f'Уникальных TMP_ID в CSV: {len(tmp_ids_in_csv)}')
                logger.info(f"Уникальных TMP_ID в CSV: {len(tmp_ids_in_csv)}")
                
                # Основной импорт
                for line_num, line in enumerate(lines[1:], start=1):  # Пропускаем заголовок
                    try:
                        # Пропускаем уже обработанные строки
                        if line_num <= skip_rows:
                            continue
                            
                        # Ограничиваем количество строк для тестирования
                        if test_lines > 0 and line_num > test_lines:
                            self.stdout.write(f'Достигнут лимит тестовых строк: {test_lines}')
                            break
                        
                        # Парсим строку
                        row = self.parse_csv_line(line, delimiter)
                        
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
                        if line_num <= 5:
                            logger.info(f"Строка {line_num}: TMP_ID={tmp_id}, NAME={name}, PRODUCER={producer_id}, SECTION={section_id}, TMC={tmc_number}")
                            self.stdout.write(f"Отладка строки {line_num}: TMP_ID={tmp_id}, NAME={name}, PRODUCER={producer_id}")
                        
                        # МИНИМАЛЬНАЯ ОБРАБОТКА - ПЕРЕНОСИМ КАК ЕСТЬ!
                        
                        # Обрабатываем только критичные пустые поля
                        if not tmp_id:
                            tmp_id = "Недоступно"
                            logger.warning(f"Строка {line_num}: Пустой TMP_ID, установлен 'Недоступно'")
                        
                        if not name:
                            name = "Недоступно"
                            logger.warning(f"Строка {line_num}: Пустое название, установлено 'Недоступно'")
                        
                        # Логируем обработку
                        if line_num <= 10 or line_num % 10000 == 0:
                            self.stdout.write(f"Строка {line_num}: TMP_ID='{tmp_id}', NAME='{name[:30]}...'")
                        
                        # Очищаем SECTION_ID от квадратных скобок и других символов
                        if section_id:
                            section_id = section_id.replace('[', '').replace(']', '').replace(';', '').strip()
                        
                        # Обрабатываем дубликаты по TMP_ID (только суффиксы)
                        original_tmp_id = tmp_id
                        counter = 1
                        while tmp_id in existing_tmp_ids:
                            tmp_id = f"{original_tmp_id}-dup{counter}"
                            counter += 1
                        
                        if tmp_id != original_tmp_id:
                            logger.warning(f"Строка {line_num}: Дубликат TMP_ID '{original_tmp_id}', изменен на '{tmp_id}'")
                        
                        # Логируем отсутствие данных (без изменений)
                        if not producer_id:
                            logger.info(f"Строка {line_num}: Товар {tmp_id} без производителя")
                        if not section_id:
                            logger.info(f"Строка {line_num}: Товар {tmp_id} без категории")
                        
                        # Логируем каждые 1000 строк для отслеживания прогресса
                        if line_num % 1000 == 0:
                            logger.info(f"Обработано строк: {line_num}/{total_lines} ({(line_num/total_lines)*100:.1f}%)")
                            if import_file:
                                # Промежуточное обновление прогресса
                                ImportFile.objects.filter(id=import_file.id).update(
                                    current_row=line_num,
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
                                if line_num <= 5:
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
                                brand = brands_cache[brand_slug]
                        else:
                            logger.warning(f"Строка {line_num}: Отсутствует производитель для товара {tmp_id}")
                        
                        # Создаем/получаем категорию (с кэшем)
                        category = None
                        if section_id:
                            # Создаем slug из SECTION_ID, а не используем SECTION_ID как slug
                            category_slug = slugify(f"category-{section_id}")
                            if category_slug in all_categories:
                                category = all_categories[category_slug]
                                if line_num <= 5:
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
                                category = categories_cache[category_slug]
                        else:
                            logger.warning(f"Строка {line_num}: Отсутствует категория для товара {tmp_id}")
                        
                        # Создаем безопасный slug для товара
                        # Очищаем название товара
                        clean_name = slugify(name)[:30] if name else 'product'
                        
                        # Очищаем TMP_ID от всех спецсимволов
                        clean_tmp_id = re.sub(r'[^a-zA-Z0-9]', '', tmp_id) if tmp_id else 'unknown'
                        
                        # Создаем базовый slug
                        base_slug = f"{clean_name}-{clean_tmp_id}"
                        
                        # Дополнительно очищаем весь slug
                        slug = slugify(base_slug)
                        
                        # Если slug пустой, создаем дефолтный
                        if not slug:
                            slug = f"product-{clean_tmp_id}"
                        
                        # Проверяем уникальность
                        counter = 1
                        original_slug = slug
                        while slug in existing_codes:
                            slug = f"{original_slug}-{counter}"
                            counter += 1
                        
                        existing_codes.add(slug)  # Добавляем в кэш
                        existing_tmp_ids.add(tmp_id)  # Добавляем в кэш
                        
                        product = Product(
                            tmp_id=tmp_id,
                            name=name[:200], 
                            slug=slug,
                            category=category,
                            brand=brand,
                            code=tmp_id,  # Используем TMP_ID как код товара
                            catalog_number=tmc_number or tmp_id,  # TMC_NUMBER как каталожный номер
                            cross_number=cross_number[:100] if cross_number else '',
                            artikyl_number=artikyl_number[:100] if artikyl_number else '',
                            applicability=model_avto[:500] if model_avto else 'Уточняйте',
                            price=0,
                            in_stock=True,
                            is_new=True,
                        )
                        
                        # Логируем создание товара для отладки
                        if line_num <= 5:
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
                            error_msg = f'Ошибка в строке {line_num}: {str(e)}'
                            self.stdout.write(self.style.ERROR(error_msg))
                            logger.error(f"Ошибка в строке {line_num}: {str(e)}")
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