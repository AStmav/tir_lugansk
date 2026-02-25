"""
Команда для импорта OE аналогов из DBF файла oe_nomer.DBF
Структура файла:
- ID_OE: Код аналога (уникальный ID 1C)
- NAME: Каталожный номер аналога
- NAME_STR: Каталожный номер без символов (очищенный)
- ID_BRENB: ID производителя (ИСПРАВЛЕНО: было ID_BREND)
- ID_TOVAR: ID товара-владельца

Запуск: python manage.py import_oe_analogs_dbf oe_nomer.DBF
"""
import os
import re
from django.core.management.base import BaseCommand
from shop.models import Product, Brand, OeKod, ImportFile
from django.utils import timezone
from collections import defaultdict
import logging

try:
    from dbfread import DBF
except ImportError:
    DBF = None

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Импорт OE аналогов из DBF файла oe_nomer.DBF (~450,000 записей)'
    
    def add_arguments(self, parser):
        parser.add_argument('dbf_file', type=str, help='Путь к DBF файлу с OE аналогами (oe_nomer.DBF)')
        parser.add_argument('--encoding', type=str, default='cp1251', help='Кодировка DBF (по умолчанию cp1251)')
        parser.add_argument('--batch-size', type=int, default=10000, help='Размер пачки для bulk_create (по умолчанию 10000)')
        parser.add_argument('--import-file-id', type=int, help='ID записи ImportFile для прогресса')
        parser.add_argument('--clear-existing', action='store_true', help='Очистить существующие аналоги')
        parser.add_argument('--test-records', type=int, default=0, help='Ограничить N записями (тестирование)')
    
    def handle(self, *args, **options):
        if not DBF:
            error_msg = '❌ Библиотека dbfread не установлена! Выполните: pip install dbfread'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            return
        
        dbf_file = options['dbf_file']
        encoding = options['encoding']
        batch_size = options['batch_size']
        import_file_id = options.get('import_file_id')
        clear_existing = options['clear_existing']
        test_records = options.get('test_records', 0)
        import_file = None
        
        self.stdout.write(f'🔄 Начинаем импорт OE аналогов из: {dbf_file}')
        self.stdout.write(f'⚙️ Размер пачки: {batch_size}')
        logger.info(f"Импорт OE аналогов из: {dbf_file}")
        
        # Настройка ImportFile
        if import_file_id:
            import_file = ImportFile.objects.filter(id=import_file_id).first()
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(
                    status='processing',
                    error_log='',
                    current_row=0,
                    created_products=0,
                    error_count=0,
                )
        
        # Проверка файла
        if not os.path.exists(dbf_file):
            error_msg = f'❌ DBF файл не найден: {dbf_file}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)
            return
        
        if not dbf_file.lower().endswith('.dbf'):
            error_msg = f'❌ Файл должен иметь расширение .dbf'
            self.stdout.write(self.style.ERROR(error_msg))
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)
            return
        
        # Очистка существующих аналогов
        if clear_existing:
            self.stdout.write('🗑️ Очищаем существующие OE аналоги...')
            deleted_count = OeKod.objects.count()
            OeKod.objects.all().delete()
            self.stdout.write(f'✅ Удалено {deleted_count} аналогов')
            logger.info(f"Удалено {deleted_count} аналогов")
        
        # Открытие DBF
        try:
            table = DBF(dbf_file, encoding=encoding)
            total_records = len(table)
            
            self.stdout.write(f'📊 Всего записей: {total_records}')
            logger.info(f"Всего записей в DBF: {total_records}")
            
            if test_records > 0:
                self.stdout.write(f'🔬 Тестовый режим: {test_records} записей')
            
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(total_rows=total_records)
        
        except Exception as e:
            error_msg = f'❌ Ошибка открытия DBF: {str(e)}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)
            return
        
        # Показ структуры файла
        try:
            first_record = next(iter(table))
            self.stdout.write('🔍 Структура DBF файла:')
            for key, value in first_record.items():
                self.stdout.write(f'   {key}: {value} ({type(value).__name__})')
            logger.info(f"Структура DBF: {list(first_record.keys())}")
        except Exception as e:
            self.stdout.write(f'⚠️ Не удалось прочитать первую запись: {e}')
        
        # КРИТИЧНО: Загружаем все товары и бренды в кэш
        self.stdout.write('📥 Загружаем товары и бренды в кэш...')
        
        products_by_tmp_id = {}
        for product in Product.objects.only('id', 'tmp_id').iterator(chunk_size=5000):
            if product.tmp_id:
                # ИСПРАВЛЕНО: Убираем суффикс -dupN из tmp_id для корректного поиска
                # В базе: "000171383-dup1", в файле: "000171383"
                clean_tmp_id = re.sub(r'-dup\d+$', '', product.tmp_id)
                products_by_tmp_id[clean_tmp_id] = product.id
        
        brands_by_code = {}
        for brand in Brand.objects.only('id', 'code').iterator(chunk_size=1000):
            if brand.code:
                brands_by_code[brand.code] = brand.id
        
        self.stdout.write(f'✅ Загружено в кэш:')
        self.stdout.write(f'   • Товаров: {len(products_by_tmp_id)}')
        self.stdout.write(f'   • Брендов: {len(brands_by_code)}')
        logger.info(f"Кэш: товары={len(products_by_tmp_id)}, бренды={len(brands_by_code)}")
        
        # Статистика
        created_count = 0
        errors = 0
        skipped_no_product = 0
        skipped_no_brand = 0
        skipped_empty = 0
        batch = []
        
        # Основной цикл импорта
        for record_num, record in enumerate(table, start=1):
            try:
                # Лимит для тестирования
                if test_records > 0 and record_num > test_records:
                    self.stdout.write(f'🔬 Достигнут лимит: {test_records}')
                    break
                
                # Извлекаем поля (пробуем разные варианты названий)
                id_oe = str(record.get('ID_oe', '') or record.get('ID_OE', '') or '').strip()
                name = str(record.get('NAME', '') or record.get('Name', '') or '').strip()
                name_str = str(record.get('NAME_STR', '') or record.get('Name_STR', '') or '').strip()
                # ИСПРАВЛЕНО: В файле поле называется ID_BRENB, а не ID_BREND!
                id_brend = str(record.get('ID_BRENB', '') or record.get('ID_brenb', '') or record.get('ID_BREND', '') or record.get('ID_brend', '') or '').strip()
                id_tovar = str(record.get('ID_TOVAR', '') or record.get('ID_tovar', '') or '').strip()
                
                # Логируем первые записи
                if record_num <= 5:
                    self.stdout.write(f'🔍 Запись {record_num}:')
                    self.stdout.write(f'   ID_oe={id_oe}, NAME={name}, Name_STR={name_str}')
                    self.stdout.write(f'   ID_BREND={id_brend}, ID_TOVAR={id_tovar}')
                    logger.info(f"Запись {record_num}: id_oe={id_oe}, id_tovar={id_tovar}")
                
                # Валидация обязательных полей
                if not id_oe or not name or not id_tovar:
                    skipped_empty += 1
                    if skipped_empty <= 10:
                        self.stdout.write(f'⚠️ Пропуск {record_num}: пустые поля')
                    continue
                
                # Пропускаем служебные записи (заголовки)
                if id_oe.lower() in ['id_oe', 'id_oe', 'character']:
                    continue
                
                # Ищем товар по ID_TOVAR
                product_id = products_by_tmp_id.get(id_tovar)
                if not product_id:
                    skipped_no_product += 1
                    if skipped_no_product <= 10:
                        self.stdout.write(f'⚠️ Товар не найден: ID_TOVAR={id_tovar} (аналог будет импортирован БЕЗ товара)')
                    # ИЗМЕНЕНО: Импортируем аналог БЕЗ товара (product=None)
                    # Товар можно будет связать позже через команду link_oe_to_products
                    product_id = None
                
                # Ищем бренд по ID_BREND (может быть пустым)
                brand_id = None
                if id_brend:
                    brand_id = brands_by_code.get(id_brend)
                    if not brand_id:
                        skipped_no_brand += 1
                        if skipped_no_brand <= 10:
                            self.stdout.write(f'⚠️ Бренд не найден: ID_BREND={id_brend}')
                
                # Создаем OE аналог
                # ИЗМЕНЕНО: product_id может быть None (товар не найден)
                # ИСПРАВЛЕНО: Всегда применяем clean_number для oe_kod_clean (name_str может содержать символы)
                oe_analog = OeKod(
                    id_oe=id_oe,
                    product_id=product_id,  # Может быть None
                    brand_id=brand_id,  # Может быть None
                    oe_kod=name[:100],  # NAME из файла
                    oe_kod_clean=OeKod.clean_number(name)[:100],  # Всегда очищаем через clean_number
                    id_tovar=id_tovar[:50]
                )
                
                batch.append(oe_analog)
                created_count += 1
                
                # Сохранение пачки
                if len(batch) >= batch_size:
                    try:
                        OeKod.objects.bulk_create(batch, ignore_conflicts=True)
                        self.stdout.write(f'💾 Сохранена пачка из {len(batch)} аналогов')
                        logger.info(f"Сохранена пачка: {len(batch)} аналогов")
                    except Exception as e:
                        self.stdout.write(f'❌ Ошибка сохранения пачки: {e}')
                        logger.error(f"Ошибка bulk_create: {e}")
                        errors += len(batch)
                    
                    batch = []
                    
                    if import_file:
                        ImportFile.objects.filter(id=import_file.id).update(
                            current_row=record_num,
                            created_products=created_count,
                            error_count=errors + skipped_no_product + skipped_no_brand
                        )
                
                # Прогресс каждые 10,000 записей
                if record_num % 10000 == 0:
                    progress = (record_num / total_records) * 100
                    self.stdout.write(f'⏳ Прогресс: {progress:.1f}% ({record_num}/{total_records})')
                    self.stdout.write(f'   Создано: {created_count}, Пропущено товаров: {skipped_no_product}')
            
            except Exception as e:
                errors += 1
                if errors <= 10:
                    self.stdout.write(f'❌ Ошибка в записи {record_num}: {e}')
                    logger.error(f"Ошибка в записи {record_num}: {e}")
                continue
        
        # Сохраняем остатки
        if batch:
            try:
                OeKod.objects.bulk_create(batch, ignore_conflicts=True)
                self.stdout.write(f'💾 Сохранена финальная пачка: {len(batch)} аналогов')
            except Exception as e:
                self.stdout.write(f'❌ Ошибка сохранения финальной пачки: {e}')
                errors += len(batch)
        
        # Финальная статистика
        total_oe_analogs = OeKod.objects.count()
        analogs_with_product = OeKod.objects.filter(product__isnull=False).count()
        analogs_without_product = OeKod.objects.filter(product__isnull=True).count()
        
        final_stats = f'''
🎉 ИМПОРТ OE АНАЛОГОВ ЗАВЕРШЕН!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Статистика:
   • Обработано записей: {record_num}
   • ✅ Создано аналогов: {created_count}
   •   └─ С товарами: {analogs_with_product}
   •   └─ БЕЗ товаров: {analogs_without_product} (можно связать позже)
   • ⚠️ Пропущено (нет бренда): {skipped_no_brand}
   • ⏭️ Пропущено (пустые поля): {skipped_empty}
   • ❌ Ошибок: {errors}
   • 📦 Всего аналогов в базе: {total_oe_analogs}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Для связывания аналогов без товаров используйте команду:
   python3 manage.py link_oe_to_products
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'''
        
        self.stdout.write(self.style.SUCCESS(final_stats))
        logger.info(f"Импорт завершен: создано={created_count}, ошибок={errors}")
        
        # Показываем примеры
        self.stdout.write('📋 Примеры импортированных аналогов:')
        sample_analogs = OeKod.objects.select_related('product', 'brand').order_by('-id')[:5]
        for analog in sample_analogs:
            brand_name = analog.brand.name if analog.brand else 'Без бренда'
            product_name = analog.product.name if analog.product else f'[Товар не найден: {analog.id_tovar}]'
            self.stdout.write(f'   • {product_name} → {brand_name} {analog.oe_kod}')
        
        # Обновление ImportFile
        if import_file:
            ImportFile.objects.filter(id=import_file.id).update(
                processed=True,
                processed_at=timezone.now(),
                status='completed',
                current_row=record_num,
                created_products=created_count,
                error_count=errors + skipped_no_product
            )
    
    @staticmethod
    def clean_number(number):
        """Удаляет все символы кроме букв и цифр"""
        if not number:
            return ''
        import re
        return re.sub(r'[^a-zA-Z0-9]', '', str(number))

