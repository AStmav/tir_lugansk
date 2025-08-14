import csv
import os
from django.core.management.base import BaseCommand
import chardet


class Command(BaseCommand):
    help = 'Отладка импорта CSV - проверяем как парсятся данные'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV файлу')
        parser.add_argument('--lines', type=int, default=10, help='Количество строк для проверки')
        parser.add_argument('--search', type=str, help='Поиск конкретного значения в CSV')

    def detect_encoding(self, file_path):
        """Определяет кодировку файла"""
        try:
            with open(file_path, 'rb') as file:
                raw_data = file.read(50000)
                result = chardet.detect(raw_data)
                return result['encoding']
        except Exception as e:
            self.stdout.write(f'Ошибка определения кодировки: {e}')
            return 'cp1251'

    def parse_csv_line(self, line, delimiter='#'):
        """Парсит строку CSV"""
        line = line.rstrip(delimiter).strip()
        fields = line.split(delimiter)
        
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

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        lines_to_check = options['lines']
        search_term = options.get('search')
        
        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f'Файл не найден: {csv_file}'))
            return

        # Определяем кодировку
        encoding = self.detect_encoding(csv_file)
        self.stdout.write(f'🔍 Используемая кодировка: {encoding}')
        
        try:
            with open(csv_file, 'r', encoding=encoding) as file:
                lines = file.readlines()
                
                # Показываем заголовок
                if len(lines) > 0:
                    self.stdout.write(f'\n📋 ЗАГОЛОВОК CSV:')
                    self.stdout.write(f'{lines[0].strip()}')
                    
                    # Проверяем структуру заголовка
                    header_fields = lines[0].strip().split('#')
                    self.stdout.write(f'\n🔧 СТРУКТУРА ЗАГОЛОВКА ({len(header_fields)} полей):')
                    for i, field in enumerate(header_fields):
                        self.stdout.write(f'  {i}: {field}')
                
                # Анализируем первые строки
                self.stdout.write(f'\n📊 АНАЛИЗ ПЕРВЫХ {lines_to_check} СТРОК:')
                self.stdout.write('-' * 80)
                
                data_lines = lines[1:lines_to_check+1] if len(lines) > 1 else []
                
                for line_num, line in enumerate(data_lines, start=2):
                    row = self.parse_csv_line(line, '#')
                    
                    self.stdout.write(f'\nСтрока {line_num}:')
                    self.stdout.write(f'  RAW: {line.strip()[:100]}...')
                    self.stdout.write(f'  TMP_ID: {row["TMP_ID"]}')
                    self.stdout.write(f'  NAME: {row["NAME"][:50]}...')
                    self.stdout.write(f'  PRODUCER: {row["PROPERTY_PRODUCER_ID"]}')
                    self.stdout.write(f'  TMC_NUMBER: {row["PROPERTY_TMC_NUMBER"]}')
                    self.stdout.write(f'  SECTION_ID: {row["SECTION_ID"]}')
                
                # Поиск конкретного значения
                if search_term:
                    self.stdout.write(f'\n🔍 ПОИСК "{search_term}" В ФАЙЛЕ:')
                    self.stdout.write('-' * 80)
                    
                    found_lines = []
                    for line_num, line in enumerate(lines, start=1):
                        if search_term.upper() in line.upper():
                            found_lines.append((line_num, line.strip()))
                    
                    if found_lines:
                        self.stdout.write(f'Найдено {len(found_lines)} совпадений:')
                        for line_num, line in found_lines[:10]:  # Показываем первые 10
                            self.stdout.write(f'  Строка {line_num}: {line[:100]}...')
                            
                            # Парсим найденную строку
                            if line_num > 1:  # Пропускаем заголовок
                                row = self.parse_csv_line(line, '#')
                                self.stdout.write(f'    → TMP_ID: {row["TMP_ID"]}, PRODUCER: {row["PROPERTY_PRODUCER_ID"]}, NAME: {row["NAME"][:30]}...')
                    else:
                        self.stdout.write(f'Совпадений не найдено')
                
                # Статистика по производителям
                self.stdout.write(f'\n📈 СТАТИСТИКА ПО ПРОИЗВОДИТЕЛЯМ (первые 1000 строк):')
                self.stdout.write('-' * 80)
                
                producer_stats = {}
                for line_num, line in enumerate(lines[1:1001], start=2):
                    try:
                        row = self.parse_csv_line(line, '#')
                        producer = row["PROPERTY_PRODUCER_ID"]
                        if producer:
                            producer_stats[producer] = producer_stats.get(producer, 0) + 1
                    except Exception as e:
                        continue
                
                # Показываем топ-10 производителей
                sorted_producers = sorted(producer_stats.items(), key=lambda x: x[1], reverse=True)
                for producer, count in sorted_producers[:15]:
                    self.stdout.write(f'  {producer}: {count} товаров')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка: {str(e)}'))
            import traceback
            traceback.print_exc() 