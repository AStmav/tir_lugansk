import csv
import os
from django.core.management.base import BaseCommand
from shop.models import Product
from shop.utils.category_import import (
    get_or_create_category_by_section_id,
    load_categories_by_section_id,
    normalize_section_id,
)


class Command(BaseCommand):
    help = 'Проверка полноты импорта товаров и поиск недостающих'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV файлу')
        parser.add_argument('--fix-missing', action='store_true', help='Импортировать недостающие товары')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        fix_missing = options['fix_missing']
        
        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f'CSV файл не найден: {csv_file}'))
            return

        self.stdout.write('📊 Анализ импорта...')
        
        # Получаем все коды товаров из БД
        db_codes = set(Product.objects.values_list('code', flat=True))
        self.stdout.write(f'💾 В базе данных: {len(db_codes)} товаров')
        
        # Читаем все коды из CSV
        csv_codes = set()
        valid_csv_rows = 0
        invalid_rows = 0
        
        with open(csv_file, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file, delimiter=';')
            
            for row_num, row in enumerate(reader, start=1):
                tmp_id = row.get('TMP_ID', '').strip()
                name = row.get('NAME', '').strip()
                
                if tmp_id and name:
                    csv_codes.add(tmp_id)
                    valid_csv_rows += 1
                else:
                    invalid_rows += 1
        
        self.stdout.write(f'📄 В CSV файле: {len(csv_codes)} валидных товаров')
        self.stdout.write(f'❌ Невалидных строк в CSV: {invalid_rows}')
        
        # Ищем недостающие товары
        missing_codes = csv_codes - db_codes
        extra_codes = db_codes - csv_codes
        
        self.stdout.write(f'\n📈 СТАТИСТИКА:')
        self.stdout.write(f'✅ Импортированных товаров: {len(db_codes)}')
        self.stdout.write(f'📝 Всего в CSV: {len(csv_codes)}')
        self.stdout.write(f'❗ Недостающих: {len(missing_codes)}')
        self.stdout.write(f'➕ Лишних в БД: {len(extra_codes)}')
        
        if missing_codes:
            self.stdout.write(f'\n❗ НЕДОСТАЮЩИЕ ТОВАРЫ ({len(missing_codes)} шт.):')
            for i, code in enumerate(list(missing_codes)[:10], 1):
                self.stdout.write(f'  {i}. {code}')
            if len(missing_codes) > 10:
                self.stdout.write(f'  ... и еще {len(missing_codes) - 10} товаров')
        
        if extra_codes:
            self.stdout.write(f'\n➕ ЛИШНИЕ В БД ({len(extra_codes)} шт.):')
            for i, code in enumerate(list(extra_codes)[:10], 1):
                self.stdout.write(f'  {i}. {code}')
            if len(extra_codes) > 10:
                self.stdout.write(f'  ... и еще {len(extra_codes) - 10} товаров')
        
        # Проверяем процент успешности
        success_rate = (len(db_codes) / len(csv_codes)) * 100 if csv_codes else 0
        self.stdout.write(f'\n📊 ПРОЦЕНТ УСПЕШНОСТИ: {success_rate:.2f}%')
        
        if success_rate >= 99:
            self.stdout.write(self.style.SUCCESS('🎉 ОТЛИЧНО! Импорт почти полный!'))
        elif success_rate >= 95:
            self.stdout.write(self.style.WARNING('⚠️ ХОРОШО, но есть недостающие товары'))
        else:
            self.stdout.write(self.style.ERROR('❌ ТРЕБУЕТСЯ ДОИМПОРТ'))
        
        # Автоматический доимпорт недостающих
        if fix_missing and missing_codes:
            self.stdout.write(f'\n🔧 ДОИМПОРТ {len(missing_codes)} недостающих товаров...')
            self.import_missing_products(csv_file, missing_codes)
        elif missing_codes:
            self.stdout.write(f'\n💡 Для доимпорта используйте: --fix-missing')

    def import_missing_products(self, csv_file, missing_codes):
        """Импорт недостающих товаров"""
        from django.utils.text import slugify
        from django.db import transaction
        from shop.models import Category, Brand
        
        imported = 0
        errors = 0
        
        # Кэш для категорий и брендов
        categories_cache = {}
        brands_cache = {}
        by_section_id = load_categories_by_section_id()
        category_stats = {'new_categories': 0}
        products_batch = []
        
        with open(csv_file, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file, delimiter=';')
            
            for row in reader:
                tmp_id = row.get('TMP_ID', '').strip()
                
                if tmp_id not in missing_codes:
                    continue
                
                try:
                    name = row.get('NAME', '').strip()
                    producer = row.get('PROPERTY_PRODUCER_ID', '').strip()
                    tmc_number = row.get('PROPERTY_TMC_NUMBER', '').strip()
                    model_avto = row.get('PROPERTY_MODEL_AVTO', '').strip()
                    section_id = row.get('SECTION_ID', '').strip()
                    
                    section_id = normalize_section_id(section_id)

                    category = None
                    if section_id:
                        category = get_or_create_category_by_section_id(
                            section_id,
                            categories_cache=categories_cache,
                            by_section_id=by_section_id,
                            stats=category_stats,
                        )
                    
                    # Бренд
                    brand = None
                    if producer:
                        producer_slug = slugify(producer)
                        if producer_slug not in brands_cache:
                            brand, _ = Brand.objects.get_or_create(
                                slug=producer_slug,
                                defaults={'name': producer}
                            )
                            brands_cache[producer_slug] = brand
                        else:
                            brand = brands_cache[producer_slug]
                    
                    # Товар
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
                    
                    if len(products_batch) >= 500:
                        with transaction.atomic():
                            Product.objects.bulk_create(products_batch, ignore_conflicts=True)
                        imported += len(products_batch)
                        self.stdout.write(f'🔧 Доимпортировано: {imported}')
                        products_batch = []
                
                except Exception as e:
                    errors += 1
        
        # Сохраняем остатки
        if products_batch:
            with transaction.atomic():
                Product.objects.bulk_create(products_batch, ignore_conflicts=True)
            imported += len(products_batch)
        
        self.stdout.write(self.style.SUCCESS(f'✅ Доимпорт завершен: {imported} товаров, ошибок: {errors}')) 