import csv
import os
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from shop.models import Brand
import chardet


class Command(BaseCommand):
    help = 'Импорт брендов из файла OE_BRANDS.csv'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV файлу с брендами')
        parser.add_argument('--encoding', type=str, default='auto', help='Кодировка файла')
        parser.add_argument('--delimiter', type=str, default=';', help='Разделитель в CSV файле')
        parser.add_argument('--test-lines', type=int, default=0, help='Ограничить импорт первыми N строками (для тестирования)')

    def detect_encoding(self, file_path):
        """Автоматически определяет кодировку файла"""
        try:
            with open(file_path, 'rb') as file:
                raw_data = file.read()
                result = chardet.detect(raw_data)
                detected_encoding = result['encoding']
                confidence = result['confidence']
                
                self.stdout.write(f'Определена кодировка: {detected_encoding} (уверенность: {confidence:.2f})')
                
                return detected_encoding
                    
        except Exception as e:
            self.stdout.write(f'Ошибка определения кодировки: {e}')
            return 'cp1251'

    def try_read_file(self, file_path, encoding):
        """Проверяет можно ли прочитать файл с данной кодировкой"""
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                for i, line in enumerate(file):
                    if i >= 10:  # Читаем первые 10 строк
                        break
                    self.stdout.write(f'Строка {i+1}: {line.strip()}')
                return True
        except UnicodeDecodeError as e:
            self.stdout.write(f'Ошибка декодирования с {encoding}: {e}')
            return False
        except Exception as e:
            self.stdout.write(f'Другая ошибка с {encoding}: {e}')
            return False

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        encoding = options['encoding']
        delimiter = options['delimiter']
        test_lines = options.get('test_lines', 0)
        
        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f'Файл не найден: {csv_file}'))
            return

        # Определяем кодировку
        if encoding == 'auto':
            encoding = self.detect_encoding(csv_file)
        
        # Пробуем разные кодировки
        encodings_to_try = [encoding, 'cp1251', 'windows-1251', 'utf-8', 'utf-8-sig', 'iso-8859-1']
        
        working_encoding = None
        self.stdout.write('\n🔍 Тестируем кодировки:')
        
        for enc in encodings_to_try:
            self.stdout.write(f'\n--- Тест кодировки: {enc} ---')
            if self.try_read_file(csv_file, enc):
                working_encoding = enc
                self.stdout.write(f'✅ Кодировка {enc} работает!')
                break
            else:
                self.stdout.write(f'❌ Кодировка {enc} не подходит')
        
        if not working_encoding:
            self.stdout.write(self.style.ERROR('Не удалось найти подходящую кодировку'))
            return

        # Основной импорт
        self.stdout.write(f'\n📥 Начинаем импорт брендов с кодировкой: {working_encoding}')
        
        created_brands = 0
        updated_brands = 0
        errors = 0
        
        try:
            with open(csv_file, 'r', encoding=working_encoding) as file:
                lines = file.readlines()
                
                # Пропускаем служебные строки (первые 3 строки: заголовок, типы, NOT NULL)
                data_lines = lines[3:] if len(lines) > 3 else lines
                
                self.stdout.write(f'📊 Всего строк данных: {len(data_lines)}')
                
                for line_num, line in enumerate(data_lines, start=1):
                    try:
                        if test_lines > 0 and line_num > test_lines:
                            self.stdout.write(f'Достигнут лимит тестовых строк: {test_lines}')
                            break
                        
                        # Убираем лишние символы и разбиваем по разделителю
                        line = line.strip()
                        if not line:
                            continue
                            
                        fields = line.split(delimiter)
                        
                        if len(fields) < 3:
                            self.stdout.write(f'⚠️ Строка {line_num}: недостаточно полей: {line}')
                            continue
                        
                        # Извлекаем данные
                        brand_code = fields[1].strip()
                        brand_name = fields[2].strip()
                        
                        # Пропускаем пустые или некорректные записи
                        if not brand_code or not brand_name or brand_code in ['code', 'Character(11,0)']:
                            continue
                        
                        # Логируем первые несколько записей
                        if line_num <= 10:
                            self.stdout.write(f'Строка {line_num}: код={brand_code}, название={brand_name}')
                        
                        # Создаем slug
                        brand_slug = brand_code.lower()
                        
                        # Создаем или обновляем бренд
                        brand, created = Brand.objects.get_or_create(slug=brand_slug, defaults={
                            'code': brand_code,
                            'name': brand_name,
                            'description': f'Бренд импортирован из справочника 1С (код: {brand_code})'
                        })
                        
                        if created:
                            created_brands += 1
                            if created_brands <= 10:  # Показываем первые 10 созданных
                                self.stdout.write(f'✅ Создан бренд: {brand_name} (slug: {brand_slug})')
                        else:
                            # Обновляем название если нужно
                            update_needed = False
                            if brand.code != brand_code:
                                brand.code = brand_code
                                update_needed = True
                            if brand.name != brand_name:
                                brand.name = brand_name
                                update_needed = True
                            if update_needed:
                                brand.save()
                                updated_brands += 1
                        
                        if (created_brands + updated_brands) % 100 == 0:
                            self.stdout.write(f'📈 Обработано: {created_brands + updated_brands} брендов')
                            
                    except Exception as e:
                        errors += 1
                        if errors <= 10:
                            self.stdout.write(f'❌ Ошибка в строке {line_num}: {str(e)}')
                        continue
                
                # Финальная статистика
                self.stdout.write(self.style.SUCCESS(f'''
📊 ИМПОРТ БРЕНДОВ ЗАВЕРШЕН:
✅ Создано брендов: {created_brands}
🔄 Обновлено брендов: {updated_brands}
❌ Ошибок: {errors}
📦 Всего брендов в базе: {Brand.objects.count()}
'''))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Критическая ошибка: {str(e)}')) 