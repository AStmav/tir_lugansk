import csv
import os
from django.core.management.base import BaseCommand
import chardet
import re


class Command(BaseCommand):
    help = 'ДЕТАЛЬНЫЙ АНАЛИЗ импорта CSV - где теряются товары'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV файлу')

    def detect_encoding(self, file_path):
        """Определяет кодировку файла"""
        try:
            with open(file_path, 'rb') as file:
                raw_data = file.read(50000)
                result = chardet.detect(raw_data)
                return result['encoding']
        except Exception as e:
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
        
        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f'Файл не найден: {csv_file}'))
            return

        # Определяем кодировку
        encoding = self.detect_encoding(csv_file)
        self.stdout.write(f'🔍 Кодировка: {encoding}')
        
        try:
            with open(csv_file, 'r', encoding=encoding) as file:
                lines = file.readlines()
                
                total_lines = len(lines)
                data_lines = total_lines - 1  # Минус заголовок
                
                self.stdout.write(f'📊 ОБЩАЯ СТАТИСТИКА:')
                self.stdout.write(f'   📝 Всего строк в файле: {total_lines}')
                self.stdout.write(f'   📦 Строк с данными: {data_lines}')
                
                # Анализируем каждую строку
                valid_rows = 0
                empty_tmp_id = 0
                empty_name = 0
                malformed_rows = 0
                duplicate_tmp_ids = 0
                invalid_chars = 0
                
                tmp_ids_seen = set()
                problem_lines = []
                
                for line_num, line in enumerate(lines[1:], start=2):  # Пропускаем заголовок
                    try:
                        row = self.parse_csv_line(line, '#')
                        
                        tmp_id = row.get('TMP_ID', '').strip()
                        name = row.get('NAME', '').strip()
                        
                        # Проверка 1: Пустые обязательные поля
                        if not tmp_id:
                            empty_tmp_id += 1
                            if len(problem_lines) < 10:
                                problem_lines.append(f'Строка {line_num}: Пустой TMP_ID')
                            continue
                            
                        if not name:
                            empty_name += 1
                            if len(problem_lines) < 10:
                                problem_lines.append(f'Строка {line_num}: Пустое название (TMP_ID: {tmp_id})')
                            continue
                        
                        # Проверка 2: Дубликаты TMP_ID
                        if tmp_id in tmp_ids_seen:
                            duplicate_tmp_ids += 1
                            if len(problem_lines) < 10:
                                problem_lines.append(f'Строка {line_num}: Дубликат TMP_ID: {tmp_id}')
                            continue
                        
                        tmp_ids_seen.add(tmp_id)
                        
                        # Проверка 3: Проблемные символы в TMP_ID или названии
                        if re.search(r'["\'\[\]<>]', tmp_id) or re.search(r'["\'\[\]<>]', name):
                            invalid_chars += 1
                            if len(problem_lines) < 10:
                                problem_lines.append(f'Строка {line_num}: Проблемные символы (TMP_ID: {tmp_id})')
                        
                        valid_rows += 1
                        
                    except Exception as e:
                        malformed_rows += 1
                        if len(problem_lines) < 10:
                            problem_lines.append(f'Строка {line_num}: Ошибка парсинга: {str(e)}')
                        continue
                
                # Результаты анализа
                self.stdout.write(f'\n🔍 ДЕТАЛЬНЫЙ АНАЛИЗ:')
                self.stdout.write(f'   ✅ Валидных строк: {valid_rows}')
                self.stdout.write(f'   ❌ Пустой TMP_ID: {empty_tmp_id}')
                self.stdout.write(f'   ❌ Пустое название: {empty_name}')
                self.stdout.write(f'   ❌ Дубликаты TMP_ID: {duplicate_tmp_ids}')
                self.stdout.write(f'   ❌ Проблемные символы: {invalid_chars}')
                self.stdout.write(f'   ❌ Ошибки парсинга: {malformed_rows}')
                
                lost_rows = data_lines - valid_rows
                self.stdout.write(f'\n💥 ПОТЕРЯНО СТРОК: {lost_rows}')
                
                if lost_rows > 0:
                    self.stdout.write(f'📋 ПРИМЕРЫ ПРОБЛЕМ:')
                    for problem in problem_lines:
                        self.stdout.write(f'   {problem}')
                
                # Рекомендации
                self.stdout.write(f'\n💡 РЕКОМЕНДАЦИИ:')
                if empty_tmp_id > 0:
                    self.stdout.write(f'   - Добавить генерацию TMP_ID для строк без ID')
                if empty_name > 0:
                    self.stdout.write(f'   - Добавить дефолтное название для товаров без названия')
                if duplicate_tmp_ids > 0:
                    self.stdout.write(f'   - Обрабатывать дубликаты TMP_ID (добавлять суффикс)')
                if invalid_chars > 0:
                    self.stdout.write(f'   - Очищать проблемные символы в TMP_ID и названиях')
                
                if lost_rows == 0:
                    self.stdout.write(self.style.SUCCESS(f'🎉 ВСЕ СТРОКИ ВАЛИДНЫ! Должно импортироваться {valid_rows} товаров'))
                else:
                    self.stdout.write(self.style.WARNING(f'⚠️  БУДЕТ ПОТЕРЯНО {lost_rows} товаров из {data_lines}'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Критическая ошибка: {str(e)}'))
            import traceback
            traceback.print_exc() 