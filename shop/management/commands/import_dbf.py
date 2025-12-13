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
import re

try:
    from dbfread import DBF
except ImportError:
    DBF = None

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Импорт товаров из DBF файла (новый формат данных 1С)'

    def add_arguments(self, parser):
        parser.add_argument('dbf_file', type=str, help='Путь к DBF файлу')
        parser.add_argument('--batch-size', type=int, default=5000, help='Размер пачки для bulk_create (по умолчанию 5000)')
        parser.add_argument('--skip-rows', type=int, default=0, help='Пропустить N записей (для продолжения)')
        parser.add_argument('--encoding', type=str, default='cp1251', help='Кодировка DBF файла (cp1251, utf-8)')
        parser.add_argument('--disable-transactions', action='store_true', help='Отключить транзакции для ускорения')
        parser.add_argument('--import-file-id', type=int, default=None, help='ID записи ImportFile для обновления прогресса')
        parser.add_argument('--clear-existing', action='store_true', help='Очистить существующие товары перед импортом')
        parser.add_argument('--test-records', type=int, default=0, help='Ограничить импорт первыми N записями (для тестирования)')

    def count_records_in_dbf(self, dbf_file, encoding='cp1251'):
        """Подсчитывает количество записей в DBF файле"""
        try:
            table = DBF(dbf_file, encoding=encoding, load=False)
            return len(table)
        except Exception as e:
            logger.error(f"Ошибка подсчета записей в DBF файле: {e}")
            return 0

    def parse_dbf_record(self, record):
        """Парсит запись из DBF файла в нужный формат"""
        return {
            'TMP_ID': str(record.get('TMP_ID', '')).strip(),
            'NAME': str(record.get('NAME', '')).strip(),
            'PROPERTY_P': str(record.get('PROPERTY_P', '')).strip(),  # бренд
            'PROPERTY_T': str(record.get('PROPERTY_T', '')).strip(),  # каталожный номер
            'PROPERTY_A': str(record.get('PROPERTY_A', '')).strip(),  # дополнительный номер
            'PROPERTY_M': str(record.get('PROPERTY_M', '')).strip(),  # применяемость
            'PROPERTY_C': str(record.get('PROPERTY_C', '')).strip(),  # кросс-код
            'SECTION_ID': str(record.get('SECTION_ID', '')).strip(),  # категория
        }

    def handle(self, *args, **options):
        if not DBF:
            error_msg = 'Библиотека dbfread не установлена! Выполните: pip install dbfread'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            return

        dbf_file = options['dbf_file']
        batch_size = options['batch_size']
        skip_rows = options['skip_rows']
        encoding = options['encoding']
        disable_transactions = options['disable_transactions']
        import_file_id = options.get('import_file_id')
        clear_existing = options.get('clear_existing', False)
        test_records = options.get('test_records', 0)
        import_file = None
        
        self.stdout.write(f'🔄 Начинаем импорт DBF файла: {dbf_file}')
        logger.info(f"Начинаем импорт DBF файла: {dbf_file}")
        
        # Настройка ImportFile для отслеживания прогресса
        if import_file_id:
            import_file = ImportFile.objects.filter(id=import_file_id).first()
            if import_file:
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

        # Проверяем существование файла
        if not os.path.exists(dbf_file):
            error_msg = f'DBF файл не найден: {dbf_file}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)
            return

        # Проверяем расширение файла
        if not dbf_file.lower().endswith('.dbf'):
            error_msg = f'Файл должен иметь расширение .dbf: {dbf_file}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)
            return

        # Очищаем существующие товары если указан флаг
        if clear_existing:
            self.stdout.write('🗑️ Очищаем существующие товары...')
            deleted_count = Product.objects.count()
            Product.objects.all().delete()
            self.stdout.write(f'✅ Удалено {deleted_count} существующих товаров')
            logger.info(f"Удалено {deleted_count} существующих товаров")
            
            # Очищаем кэши
            existing_tmp_ids = set()
            existing_codes = set()
            all_categories = {}
            all_brands = {}
        else:
            # Загружаем существующие данные в память для быстрого поиска
            self.stdout.write('📥 Загружаем существующие данные в память...')
            
            existing_tmp_ids = set(Product.objects.values_list('tmp_id', flat=True))
            existing_codes = set(Product.objects.values_list('slug', flat=True))
            all_categories = {cat.slug: cat for cat in Category.objects.all()}
            all_brands = {brand.slug: brand for brand in Brand.objects.all()}
            for brand in Brand.objects.all():
                if brand.code:
                    all_brands.setdefault(brand.code.lower(), brand)
            
            self.stdout.write(f'📊 Загружено:')
            self.stdout.write(f'   • {len(existing_tmp_ids)} товаров по TMP_ID')
            self.stdout.write(f'   • {len(existing_codes)} товаров по slug')
            self.stdout.write(f'   • {len(all_categories)} категорий')
            self.stdout.write(f'   • {len(all_brands)} брендов')
            
            logger.info(f"Загружено данных: товары={len(existing_tmp_ids)}, категории={len(all_categories)}, бренды={len(all_brands)}")

        # Пытаемся открыть DBF файл
        try:
            table = DBF(dbf_file, encoding=encoding)
            total_records = len(table)
            self.stdout.write(f'📋 Всего записей в DBF файле: {total_records}')
            logger.info(f"Всего записей в DBF файле: {total_records}")
            
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(total_rows=total_records)
                
        except Exception as e:
            error_msg = f'Ошибка открытия DBF файла: {str(e)}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)
            return

        # Инициализируем переменные
        categories_cache = {}
        brands_cache = {}
        stats = defaultdict(int)
        processed_records = 0
        errors = 0
        products_batch = []

        # Выводим структуру первой записи для отладки
        try:
            first_record = next(iter(table))
            self.stdout.write('🔍 Структура DBF файла:')
            for key, value in first_record.items():
                self.stdout.write(f'   {key}: {value} ({type(value).__name__})')
            logger.info(f"Структура DBF: {list(first_record.keys())}")
        except Exception as e:
            self.stdout.write(f'⚠️ Не удалось прочитать первую запись: {e}')

        try:
            if not disable_transactions:
                connection.autocommit = False

            # Основной цикл обработки записей
            for record_num, record in enumerate(table, start=1):
                try:
                    # Пропускаем уже обработанные записи
                    if record_num <= skip_rows:
                        continue
                        
                    # Ограничиваем количество записей для тестирования
                    if test_records > 0 and record_num > test_records:
                        self.stdout.write(f'🔬 Достигнут лимит тестовых записей: {test_records}')
                        break

                    # Парсим данные из DBF записи
                    data = self.parse_dbf_record(record)
                    
                    tmp_id = data.get('TMP_ID', '').strip()
                    name = data.get('NAME', '').strip()
                    producer = data.get('PROPERTY_P', '').strip()
                    catalog_number = data.get('PROPERTY_T', '').strip()  # каталожный номер
                    artikyl_number = data.get('PROPERTY_A', '').strip()  # дополнительный номер
                    applicability = data.get('PROPERTY_M', '').strip()  # применяемость
                    cross_number = data.get('PROPERTY_C', '').strip()  # кросс-код
                    section_id = data.get('SECTION_ID', '').strip()  # категория

                    # Логируем первые записи для отладки
                    if record_num <= 5:
                        logger.info(f"Запись {record_num}: TMP_ID={tmp_id}, NAME={name}, PRODUCER={producer}, SECTION={section_id}")
                        self.stdout.write(f"🔍 Запись {record_num}: TMP_ID={tmp_id}, NAME={name[:30]}...")

                    # Обрабатываем критичные пустые поля
                    if not tmp_id:
                        tmp_id = f"auto-{record_num}"
                        logger.warning(f"Запись {record_num}: Пустой TMP_ID, установлен '{tmp_id}'")
                        
                    if not name:
                        name = "Товар без названия"
                        logger.warning(f"Запись {record_num}: Пустое название, установлено '{name}'")

                    # Обрабатываем дубликаты по TMP_ID
                    original_tmp_id = tmp_id
                    counter = 1
                    while tmp_id in existing_tmp_ids:
                        tmp_id = f"{original_tmp_id}-dup{counter}"
                        counter += 1
                        
                    if tmp_id != original_tmp_id:
                        logger.warning(f"Запись {record_num}: Дубликат TMP_ID '{original_tmp_id}', изменен на '{tmp_id}'")

                    # Создаем/получаем бренд
                    brand = None
                    if producer:
                        brand_code = producer.lower()
                        if brand_code in all_brands:
                            brand = all_brands[brand_code]
                        elif brand_code not in brands_cache:
                            brand, created = Brand.objects.get_or_create(slug=brand_code, defaults={
                                'code': producer,
                                'name': producer
                            })
                            all_brands[brand_code] = brand
                            brands_cache[brand_code] = brand
                            if created:
                                stats['new_brands'] += 1
                                self.stdout.write(f'🏭 Создан бренд: {brand.name}')
                                logger.info(f"Создан новый бренд: {brand.name}")
                        else:
                            brand = brands_cache[brand_code]

                    # Создаем/получаем категорию
                    category = None
                    if section_id:
                        category_slug = slugify(f"category-{section_id}")
                        if category_slug in all_categories:
                            category = all_categories[category_slug]
                        elif category_slug not in categories_cache:
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
                                self.stdout.write(f'📁 Создана категория: {category.name}')
                                logger.info(f"Создана новая категория: {category.name}")
                        else:
                            category = categories_cache[category_slug]

                    # Создаем безопасный slug для товара
                    clean_name = slugify(name)[:30] if name else 'product'
                    clean_tmp_id = re.sub(r'[^a-zA-Z0-9]', '', tmp_id) if tmp_id else 'unknown'
                    base_slug = f"{clean_name}-{clean_tmp_id}"
                    slug = slugify(base_slug)
                    
                    if not slug:
                        slug = f"product-{clean_tmp_id}"
                    
                    # Проверяем уникальность slug
                    counter = 1
                    original_slug = slug
                    while slug in existing_codes:
                        slug = f"{original_slug}-{counter}"
                        counter += 1
                    
                    existing_codes.add(slug)
                    existing_tmp_ids.add(tmp_id)

                    # Создаем товар
                    product = Product(
                        tmp_id=tmp_id,
                        name=name[:200], 
                        slug=slug,
                        category=category,
                        brand=brand,
                        code=tmp_id,
                        catalog_number=catalog_number[:50] if catalog_number else tmp_id,
                        cross_number=cross_number[:100] if cross_number else '',
                        artikyl_number=artikyl_number[:100] if artikyl_number else '',
                        applicability=applicability[:500] if applicability else 'Уточняйте',
                        price=0,  # Цена будет обновляться отдельно
                        in_stock=True,
                        is_new=True,
                    )

                    products_batch.append(product)
                    stats['new_products'] += 1
                    processed_records += 1

                    # Логируем прогресс
                    if processed_records % 1000 == 0:
                        progress = (processed_records / total_records) * 100
                        self.stdout.write(f'⏳ Прогресс: {progress:.1f}% ({processed_records}/{total_records}) | Создано товаров: {stats["new_products"]}')
                        logger.info(f"Прогресс: {progress:.1f}%, создано товаров: {stats['new_products']}")
                        
                        if import_file:
                            ImportFile.objects.filter(id=import_file.id).update(
                                current_row=processed_records,
                                processed_rows=processed_records,
                                created_products=stats['new_products'],
                                error_count=errors,
                            )

                    # Сохраняем пачку товаров
                    if len(products_batch) >= batch_size:
                        self._save_products_batch(products_batch)
                        logger.info(f"Сохранена пачка товаров: {len(products_batch)}")
                        products_batch = []
                        
                        if import_file:
                            ImportFile.objects.filter(id=import_file.id).update(
                                processed_rows=processed_records,
                                created_products=stats['new_products']
                            )

                except Exception as e:
                    errors += 1
                    if errors <= 10:
                        error_msg = f'Ошибка в записи {record_num}: {str(e)}'
                        self.stdout.write(self.style.ERROR(error_msg))
                        logger.error(f"Ошибка в записи {record_num}: {str(e)}")
                    
                    if import_file:
                        ImportFile.objects.filter(id=import_file.id).update(error_count=errors)
                    continue

            # Сохраняем оставшиеся товары
            if products_batch:
                self._save_products_batch(products_batch)
                logger.info(f"Сохранена финальная пачка товаров: {len(products_batch)}")

            if not disable_transactions:
                connection.autocommit = True

            # Финальная статистика
            final_stats = (
                f'\n🎉 Импорт DBF завершен!\n'
                f'📊 Обработано записей: {processed_records}\n'
                f'📁 Создано категорий: {stats["new_categories"]}\n'
                f'🏭 Создано брендов: {stats["new_brands"]}\n'
                f'📦 Создано товаров: {stats["new_products"]}\n'
                f'⚠️ Ошибок: {errors}'
            )

            # Логируем без эмодзи для избежания проблем с кодировкой
            final_stats_log = (
                f'Импорт DBF завершен! '
                f'Обработано записей: {processed_records}, '
                f'Создано категорий: {stats["new_categories"]}, '
                f'Создано брендов: {stats["new_brands"]}, '
                f'Создано товаров: {stats["new_products"]}, '
                f'Ошибок: {errors}'
            )

            self.stdout.write(self.style.SUCCESS(final_stats))
            logger.info(final_stats_log)
            
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(
                    processed=True,
                    processed_at=timezone.now(),
                    status='completed',
                    current_row=processed_records,
                    processed_rows=processed_records,
                    created_products=stats['new_products'],
                    error_count=errors,
                )

        except Exception as e:
            error_msg = f'Критическая ошибка импорта DBF: {str(e)}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            
            if not disable_transactions:
                connection.autocommit = True
                
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)

    def _save_products_batch(self, products_batch):
        """Сохраняет пачку товаров в базу данных"""
        try:
            logger.info(f"Попытка сохранения пачки из {len(products_batch)} товаров")
            
            created_products = Product.objects.bulk_create(products_batch, ignore_conflicts=True)
            actual_count = len(created_products)
            
            logger.info(f"Фактически создано товаров: {actual_count} из {len(products_batch)}")
            
            if actual_count < len(products_batch):
                logger.warning(f"Пропущено товаров из-за конфликтов: {len(products_batch) - actual_count}")
            
            self.stdout.write(f'💾 Сохранена пачка из {len(products_batch)} товаров')
            
        except Exception as e:
            error_msg = f'Ошибка сохранения пачки товаров: {str(e)}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            
            # Пытаемся сохранить по одному товару
            for product in products_batch:
                try:
                    product.save()
                    logger.info(f"Товар {product.tmp_id} сохранен по одному")
                except Exception as single_error:
                    logger.error(f"Не удалось сохранить товар {product.tmp_id}: {str(single_error)}")
