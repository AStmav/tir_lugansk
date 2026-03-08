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
        parser.add_argument(
            '--update-mode',
            choices=['create_only', 'update', 'skip'],
            default='update',
            help='Режим обработки существующих товаров: create_only (создать дубликат), update (обновить), skip (пропустить)'
        )

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
        update_mode = options.get('update_mode', 'update')
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

        # Бренд по умолчанию для товаров без производителя (PROPERTY_P) — чтобы такие товары тоже импортировались
        default_brand, _ = Brand.objects.get_or_create(
            slug='bez-brenda',
            defaults={'name': 'Без бренда', 'code': '__NO_BRAND__'}
        )

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
        products_batch_create = []  # Для новых товаров
        products_batch_update = []  # Для обновления существующих
        
        # Загружаем все существующие товары в память для быстрой проверки
        self.stdout.write('📥 Загрузка существующих товаров из БД...')
        existing_products_dict = {p.tmp_id: p for p in Product.objects.all()}
        self.stdout.write(f'✅ Загружено {len(existing_products_dict):,} существующих товаров')
        logger.info(f"Загружено {len(existing_products_dict)} существующих товаров")
        
        # Информация о режиме обработки
        mode_descriptions = {
            'create_only': '🔸 Режим: СОЗДАНИЕ (дубликаты → -dup)',
            'update': '🔄 Режим: ОБНОВЛЕНИЕ (дубликаты → обновить)',
            'skip': '⏭️  Режим: ПРОПУСК (дубликаты → пропустить)',
        }
        self.stdout.write(mode_descriptions.get(update_mode, ''))
        logger.info(f"Режим обработки: {update_mode}")

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
                    
                    # ИСПРАВЛЕНО: Если catalog_number пустой, используем tmp_id
                    # Это нужно для корректного заполнения catalog_number_clean
                    if not catalog_number:
                        catalog_number = tmp_id

                    # Создаем/получаем бренд (СНАЧАЛА бренд, потом товар!)
                    # ВАЖНО: PROPERTY_P содержит ID_brend (код бренда из 1С)
                    brand = None
                    if producer:
                        # producer = PROPERTY_P = ID_brend из файла
                        brand_id = producer  # Это ID_brend, не slug!
                        
                        if brand_id in all_brands:
                            brand = all_brands[brand_id]
                        elif brand_id not in brands_cache:
                            # Ищем бренд по полю code (где хранится ID_brend)
                            try:
                                brand = Brand.objects.get(code=brand_id)
                                all_brands[brand_id] = brand
                                brands_cache[brand_id] = brand
                            except Brand.DoesNotExist:
                                # Бренд не найден - создаем новый
                                brand_slug = slugify(f'brand-{brand_id}')
                                brand, created = Brand.objects.get_or_create(
                                    code=brand_id,
                                    defaults={
                                        'slug': brand_slug,
                                        'name': f'Бренд {brand_id}',
                                        'description': f'Автоматически созданный бренд (ID: {brand_id})'
                                    }
                                )
                                all_brands[brand_id] = brand
                                brands_cache[brand_id] = brand
                                if created:
                                    stats['new_brands'] += 1
                                    self.stdout.write(f'🏭 Создан бренд: {brand.name} (ID: {brand_id})')
                                    logger.info(f"Создан новый бренд: {brand.name} (ID: {brand_id})")
                        else:
                            brand = brands_cache[brand_id]

                    if brand is None:
                        brand = default_brand

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

                    # ============================================================
                    # НОВАЯ ЛОГИКА: Обработка дубликатов в зависимости от режима
                    # ============================================================
                    
                    existing_product = existing_products_dict.get(tmp_id)
                    
                    if existing_product and update_mode == 'update':
                        # ========== РЕЖИМ ОБНОВЛЕНИЯ ==========
                        # Обновляем существующий товар
                        existing_product.name = name[:200]
                        existing_product.brand = brand
                        existing_product.category = category
                        # ИСПРАВЛЕНО: Если catalog_number пустой, используем tmp_id
                        catalog_number_for_clean = catalog_number if catalog_number else tmp_id
                        existing_product.catalog_number = catalog_number_for_clean[:50]
                        existing_product.cross_number = cross_number[:100] if cross_number else ''
                        existing_product.artikyl_number = artikyl_number[:100] if artikyl_number else ''
                        # ИСПРАВЛЕНО: Всегда заполняем очищенные номера
                        existing_product.catalog_number_clean = Product.clean_number(catalog_number_for_clean)[:50]
                        existing_product.artikyl_number_clean = Product.clean_number(artikyl_number)[:100] if artikyl_number else ''
                        existing_product.applicability = applicability[:500] if applicability else 'Уточняйте'
                        
                        products_batch_update.append(existing_product)
                        stats['updated_products'] += 1
                        
                    elif existing_product and update_mode == 'skip':
                        # ========== РЕЖИМ ПРОПУСКА ==========
                        # Пропускаем существующий товар
                        stats['skipped_products'] += 1
                        
                    elif existing_product and update_mode == 'create_only':
                        # ========== РЕЖИМ СОЗДАНИЯ ДУБЛИКАТОВ (старый) ==========
                        # Создаём дубликат с суффиксом
                        original_tmp_id = tmp_id
                        counter = 1
                        # Ищем свободный tmp_id с суффиксом
                        while (tmp_id in existing_products_dict or 
                               any(p.tmp_id == tmp_id for p in products_batch_create)):
                            tmp_id = f"{original_tmp_id}-dup{counter}"
                            counter += 1
                        
                        logger.warning(f"Запись {record_num}: Дубликат TMP_ID '{original_tmp_id}', изменен на '{tmp_id}'")
                        
                        # Создаём товар с новым tmp_id (логика ниже)
                        # Флаг что это создание нового товара
                        existing_product = None
                        
                    # else: existing_product is None - создаём новый товар
                    
                    # ========== СОЗДАНИЕ НОВОГО ТОВАРА ==========
                    if not existing_product or update_mode == 'create_only':
                        # Создаем безопасный slug для товара
                        clean_name = slugify(name)[:30] if name else 'product'
                        clean_tmp_id = re.sub(r'[^a-zA-Z0-9]', '', tmp_id) if tmp_id else 'unknown'
                        base_slug = f"{clean_name}-{clean_tmp_id}"
                        slug = slugify(base_slug)
                        
                        if not slug:
                            slug = f"product-{clean_tmp_id}"
                        
                        # Проверяем уникальность slug (среди уже созданных в этом импорте)
                        counter = 1
                        original_slug = slug
                        existing_slugs = set(p.slug for p in products_batch_create)
                        while slug in existing_slugs:
                            slug = f"{original_slug}-{counter}"
                            counter += 1

                        # Создаем товар
                        # ВАЖНО: Заполняем очищенные номера вручную, 
                        # так как при bulk_create метод save() не вызывается
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
                            # ИСПРАВЛЕНО: Всегда заполняем очищенные номера (даже если catalog_number = tmp_id)
                            catalog_number_clean=Product.clean_number(catalog_number if catalog_number else tmp_id)[:50],
                            artikyl_number_clean=Product.clean_number(artikyl_number)[:100] if artikyl_number else '',
                            applicability=applicability[:500] if applicability else 'Уточняйте',
                            price=0,  # Цена будет обновляться отдельно
                            in_stock=True,
                            is_new=True,
                        )

                        products_batch_create.append(product)
                        stats['new_products'] += 1

                    processed_records += 1

                    # Логируем прогресс
                    if processed_records % 1000 == 0:
                        progress = (processed_records / total_records) * 100
                        self.stdout.write(
                            f'⏳ Прогресс: {progress:.1f}% ({processed_records}/{total_records}) | '
                            f'Создано: {stats["new_products"]} | Обновлено: {stats["updated_products"]} | '
                            f'Пропущено: {stats["skipped_products"]}'
                        )
                        logger.info(
                            f"Прогресс: {progress:.1f}%, создано: {stats['new_products']}, "
                            f"обновлено: {stats['updated_products']}, пропущено: {stats['skipped_products']}"
                        )
                        
                        if import_file:
                            ImportFile.objects.filter(id=import_file.id).update(
                                current_row=processed_records,
                                processed_rows=processed_records,
                                created_products=stats['new_products'],
                                updated_products=stats['updated_products'],
                                error_count=errors,
                            )

                    # Сохраняем пачку НОВЫХ товаров
                    if len(products_batch_create) >= batch_size:
                        self._save_products_batch(products_batch_create)
                        logger.info(f"Создано товаров в пачке: {len(products_batch_create)}")
                        products_batch_create = []
                    
                    # Сохраняем пачку ОБНОВЛЁННЫХ товаров
                    if len(products_batch_update) >= batch_size:
                        # Используем bulk_update для обновления
                        Product.objects.bulk_update(
                            products_batch_update,
                            fields=['name', 'brand', 'category', 'catalog_number', 'cross_number', 
                                   'artikyl_number', 'catalog_number_clean', 'artikyl_number_clean', 'applicability'],
                            batch_size=batch_size
                        )
                        logger.info(f"Обновлено товаров в пачке: {len(products_batch_update)}")
                        products_batch_update = []

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
            if products_batch_create:
                self._save_products_batch(products_batch_create)
                logger.info(f"Сохранена финальная пачка НОВЫХ товаров: {len(products_batch_create)}")
            
            # Сохраняем оставшиеся обновления
            if products_batch_update:
                Product.objects.bulk_update(
                    products_batch_update,
                    fields=['name', 'brand', 'category', 'catalog_number', 'cross_number', 
                           'artikyl_number', 'catalog_number_clean', 'artikyl_number_clean', 'applicability'],
                    batch_size=batch_size
                )
                logger.info(f"Сохранена финальная пачка ОБНОВЛЁННЫХ товаров: {len(products_batch_update)}")

            if not disable_transactions:
                connection.autocommit = True

            # Финальная статистика
            final_stats = (
                f'\n🎉 Импорт DBF завершен!\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'📊 Обработано записей: {processed_records}\n'
                f'📁 Создано категорий: {stats["new_categories"]}\n'
                f'🏭 Создано брендов: {stats["new_brands"]}\n'
                f'✅ Создано товаров: {stats["new_products"]}\n'
                f'🔄 Обновлено товаров: {stats["updated_products"]}\n'
                f'⏭️ Пропущено товаров: {stats["skipped_products"]}\n'
                f'⚠️ Ошибок: {errors}\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
            )

            # Логируем без эмодзи для избежания проблем с кодировкой
            final_stats_log = (
                f'Импорт DBF завершен! '
                f'Обработано записей: {processed_records}, '
                f'Создано категорий: {stats["new_categories"]}, '
                f'Создано брендов: {stats["new_brands"]}, '
                f'Создано товаров: {stats["new_products"]}, '
                f'Обновлено товаров: {stats["updated_products"]}, '
                f'Пропущено товаров: {stats["skipped_products"]}, '
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
