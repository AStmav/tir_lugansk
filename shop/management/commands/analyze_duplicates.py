import csv
import os
from collections import defaultdict, Counter
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Анализ дубликатов изображений и товаров в CSV'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV файлу')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        
        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f'CSV файл не найден: {csv_file}'))
            return

        self.stdout.write('🔍 Анализ дубликатов в CSV...')
        
        # Словари для анализа
        products_by_image = defaultdict(list)  # image_path -> [product_codes]
        section_counter = Counter()  # section_id -> count
        name_counter = Counter()  # name -> count
        producer_counter = Counter()  # producer -> count
        
        total_rows = 0
        valid_rows = 0
        
        with open(csv_file, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file, delimiter=';')
            
            for row in reader:
                total_rows += 1
                
                tmp_id = (row.get('TMP_ID') or '').strip()
                name = (row.get('NAME') or '').strip()
                producer = (row.get('PROPERTY_PRODUCER_ID') or '').strip()
                section_id = (row.get('SECTION_ID') or '').strip()
                
                if not tmp_id or not name:
                    continue
                    
                valid_rows += 1
                
                # Очищаем SECTION_ID
                if section_id:
                    section_id = section_id.replace('[', '').replace(']', '').replace(';', '')
                
                # Путь к изображению
                if section_id:
                    image_path = f'{section_id}/{tmp_id}.jpg'
                    products_by_image[image_path].append({
                        'code': tmp_id,
                        'name': name,
                        'producer': producer,
                        'section': section_id
                    })
                
                # Счетчики
                section_counter[section_id] += 1
                name_counter[name] += 1
                if producer:
                    producer_counter[producer] += 1
        
        # Анализ результатов
        self.stdout.write(f'\n📊 ОБЩАЯ СТАТИСТИКА:')
        self.stdout.write(f'📄 Всего строк в CSV: {total_rows}')
        self.stdout.write(f'✅ Валидных товаров: {valid_rows}')
        self.stdout.write(f'📁 Уникальных категорий: {len(section_counter)}')
        self.stdout.write(f'🏭 Уникальных производителей: {len(producer_counter)}')
        
        # Топ категорий
        self.stdout.write(f'\n📦 ТОП-10 КАТЕГОРИЙ ПО КОЛИЧЕСТВУ ТОВАРОВ:')
        for section, count in section_counter.most_common(10):
            self.stdout.write(f'  📂 {section}: {count} товаров')
        
        # Топ производителей
        self.stdout.write(f'\n🏭 ТОП-10 ПРОИЗВОДИТЕЛЕЙ:')
        for producer, count in producer_counter.most_common(10):
            producer_name = producer if producer else 'Без производителя'
            self.stdout.write(f'  🔧 {producer_name}: {count} товаров')
        
        # Анализ дубликатов названий
        duplicate_names = {name: count for name, count in name_counter.items() if count > 1}
        self.stdout.write(f'\n📝 ДУБЛИКАТЫ НАЗВАНИЙ:')
        self.stdout.write(f'🔄 Товаров с дублированными названиями: {len(duplicate_names)}')
        
        if duplicate_names:
            self.stdout.write(f'\n🔍 ТОП-10 САМЫХ ЧАСТЫХ НАЗВАНИЙ:')
            for name, count in Counter(duplicate_names).most_common(10):
                self.stdout.write(f'  📋 "{name[:60]}..." встречается {count} раз')
        
        # Анализ изображений
        self.stdout.write(f'\n🖼️ АНАЛИЗ ИЗОБРАЖЕНИЙ:')
        
        # Проверяем существование файлов
        existing_images = 0
        missing_images = 0
        images_with_multiple_products = 0
        
        for image_path, products in products_by_image.items():
            full_path = os.path.join(settings.BASE_DIR, 'images', image_path)
            
            if os.path.exists(full_path):
                existing_images += 1
                if len(products) > 1:
                    images_with_multiple_products += 1
            else:
                missing_images += 1
        
        total_image_paths = len(products_by_image)
        
        self.stdout.write(f'📷 Всего уникальных путей к изображениям: {total_image_paths}')
        self.stdout.write(f'✅ Существующих файлов: {existing_images}')
        self.stdout.write(f'❌ Отсутствующих файлов: {missing_images}')
        self.stdout.write(f'🔄 Изображений для нескольких товаров: {images_with_multiple_products}')
        
        # Примеры изображений для нескольких товаров
        if images_with_multiple_products > 0:
            self.stdout.write(f'\n🔄 ПРИМЕРЫ ИЗОБРАЖЕНИЙ ДЛЯ НЕСКОЛЬКИХ ТОВАРОВ:')
            count = 0
            for image_path, products in products_by_image.items():
                if len(products) > 1:
                    full_path = os.path.join(settings.BASE_DIR, 'images', image_path)
                    if os.path.exists(full_path):
                        self.stdout.write(f'  📷 {image_path} используется для {len(products)} товаров:')
                        for product in products[:3]:  # Показываем первые 3
                            self.stdout.write(f'    • {product["code"]} - {product["name"][:40]}...')
                        if len(products) > 3:
                            self.stdout.write(f'    ... и еще {len(products) - 3} товаров')
                        count += 1
                        if count >= 5:  # Показываем только первые 5 примеров
                            break
        
        # Рекомендации
        coverage_percent = (existing_images / total_image_paths * 100) if total_image_paths > 0 else 0
        self.stdout.write(f'\n💡 РЕКОМЕНДАЦИИ:')
        
        if coverage_percent < 50:
            self.stdout.write('❗ Критически мало изображений - нужно добавить файлы')
        elif coverage_percent < 80:
            self.stdout.write('⚠️ Можно улучшить покрытие изображениями')
        else:
            self.stdout.write('✅ Хорошее покрытие изображениями')
        
        if images_with_multiple_products > 0:
            self.stdout.write('🔄 Есть изображения для нескольких товаров - это нормально для аналогов')
        
        if duplicate_names:
            self.stdout.write('📝 Много товаров с одинаковыми названиями - возможно аналоги или вариации')
            
        self.stdout.write(f'📊 Покрытие изображениями: {coverage_percent:.1f}%') 