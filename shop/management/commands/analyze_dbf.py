import os
from django.core.management.base import BaseCommand
import re

try:
    from dbfread import DBF
except ImportError:
    DBF = None


class Command(BaseCommand):
    help = 'ДЕТАЛЬНЫЙ АНАЛИЗ импорта DBF - структура данных и потенциальные проблемы'

    def add_arguments(self, parser):
        parser.add_argument('dbf_file', type=str, help='Путь к DBF файлу')
        parser.add_argument('--encoding', type=str, default='cp1251', help='Кодировка DBF файла (по умолчанию cp1251)')
        parser.add_argument('--sample-size', type=int, default=10, help='Количество записей для показа примеров (по умолчанию 10)')

    def parse_dbf_record(self, record):
        """Парсит запись из DBF файла"""
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
            return

        dbf_file = options['dbf_file']
        encoding = options['encoding']
        sample_size = options['sample_size']
        
        if not os.path.exists(dbf_file):
            self.stdout.write(self.style.ERROR(f'🚫 Файл не найден: {dbf_file}'))
            return

        if not dbf_file.lower().endswith('.dbf'):
            self.stdout.write(self.style.ERROR(f'🚫 Файл должен иметь расширение .dbf: {dbf_file}'))
            return

        try:
            # Открываем DBF файл
            table = DBF(dbf_file, encoding=encoding)
            total_records = len(table)
            
            self.stdout.write(f'📊 ОБЩАЯ СТАТИСТИКА DBF ФАЙЛА:')
            self.stdout.write(f'   📁 Файл: {os.path.basename(dbf_file)}')
            self.stdout.write(f'   📏 Размер файла: {os.path.getsize(dbf_file) / (1024*1024):.2f} MB')
            self.stdout.write(f'   📋 Всего записей: {total_records}')
            self.stdout.write(f'   🔤 Кодировка: {encoding}')
            
            # Показываем структуру таблицы
            field_info = table.field_names
            self.stdout.write(f'\n🗂️ СТРУКТУРА ТАБЛИЦЫ:')
            for i, field_name in enumerate(field_info, 1):
                self.stdout.write(f'   {i:2d}. {field_name}')
            
            # Анализируем записи
            valid_records = 0
            empty_tmp_id = 0
            empty_name = 0
            empty_producer = 0
            empty_section_id = 0
            duplicate_tmp_ids = 0
            invalid_chars = 0
            
            tmp_ids_seen = set()
            problem_records = []
            sample_records = []
            producers = set()
            sections = set()
            
            self.stdout.write(f'\n🔍 АНАЛИЗ ДАННЫХ:')
            
            for record_num, record in enumerate(table, start=1):
                try:
                    # Парсим запись
                    data = self.parse_dbf_record(record)
                    
                    tmp_id = data.get('TMP_ID', '').strip()
                    name = data.get('NAME', '').strip()
                    producer = data.get('PROPERTY_P', '').strip()
                    section_id = data.get('SECTION_ID', '').strip()

                    # Сохраняем примеры для отображения
                    if len(sample_records) < sample_size:
                        sample_records.append({
                            'num': record_num,
                            'tmp_id': tmp_id,
                            'name': name[:40] + '...' if len(name) > 40 else name,
                            'producer': producer,
                            'section': section_id
                        })

                    # Проверки на проблемы
                    has_problems = False
                    
                    # Проверка 1: Пустые обязательные поля
                    if not tmp_id:
                        empty_tmp_id += 1
                        has_problems = True
                        if len(problem_records) < 10:
                            problem_records.append(f'Запись {record_num}: Пустой TMP_ID')
                            
                    if not name:
                        empty_name += 1
                        has_problems = True
                        if len(problem_records) < 10:
                            problem_records.append(f'Запись {record_num}: Пустое название (TMP_ID: {tmp_id})')
                    
                    # Проверка 2: Дубликаты TMP_ID
                    if tmp_id and tmp_id in tmp_ids_seen:
                        duplicate_tmp_ids += 1
                        has_problems = True
                        if len(problem_records) < 10:
                            problem_records.append(f'Запись {record_num}: Дубликат TMP_ID: {tmp_id}')
                    elif tmp_id:
                        tmp_ids_seen.add(tmp_id)
                    
                    # Проверка 3: Проблемные символы
                    if tmp_id and re.search(r'["\'\[\]<>]', tmp_id):
                        invalid_chars += 1
                        has_problems = True
                        if len(problem_records) < 10:
                            problem_records.append(f'Запись {record_num}: Проблемные символы в TMP_ID: {tmp_id}')
                    
                    if name and re.search(r'["\'\[\]<>]', name):
                        invalid_chars += 1
                        has_problems = True
                        if len(problem_records) < 10:
                            problem_records.append(f'Запись {record_num}: Проблемные символы в названии')
                    
                    # Дополнительные проверки
                    if not producer:
                        empty_producer += 1
                    else:
                        producers.add(producer)
                        
                    if not section_id:
                        empty_section_id += 1
                    else:
                        sections.add(section_id)
                    
                    if not has_problems:
                        valid_records += 1
                        
                except Exception as e:
                    if len(problem_records) < 10:
                        problem_records.append(f'Запись {record_num}: Ошибка парсинга: {str(e)}')
                    continue

            # Результаты анализа
            self.stdout.write(f'\n📋 РЕЗУЛЬТАТЫ АНАЛИЗА:')
            self.stdout.write(f'   ✅ Валидных записей: {valid_records}')
            self.stdout.write(f'   ❌ Пустой TMP_ID: {empty_tmp_id}')
            self.stdout.write(f'   ❌ Пустое название: {empty_name}')
            self.stdout.write(f'   ❌ Дубликаты TMP_ID: {duplicate_tmp_ids}')
            self.stdout.write(f'   ❌ Проблемные символы: {invalid_chars}')
            self.stdout.write(f'   ⚠️ Без производителя: {empty_producer}')
            self.stdout.write(f'   ⚠️ Без категории: {empty_section_id}')
            
            lost_records = total_records - valid_records
            success_rate = (valid_records / total_records * 100) if total_records > 0 else 0
            
            self.stdout.write(f'\n💥 ПОТЕНЦИАЛЬНЫЕ ПОТЕРИ:')
            self.stdout.write(f'   📉 Потеряно записей: {lost_records}')
            self.stdout.write(f'   📊 Успешность импорта: {success_rate:.1f}%')

            # Статистика по производителям и категориям
            self.stdout.write(f'\n📈 СТАТИСТИКА:')
            self.stdout.write(f'   🏭 Уникальных производителей: {len(producers)}')
            self.stdout.write(f'   📁 Уникальных категорий: {len(sections)}')

            # Примеры записей
            if sample_records:
                self.stdout.write(f'\n📄 ПРИМЕРЫ ЗАПИСЕЙ (первые {len(sample_records)}):')
                for sample in sample_records:
                    self.stdout.write(f'   {sample["num"]:3d}: {sample["tmp_id"]:<12} | {sample["name"]:<40} | {sample["producer"]:<15} | {sample["section"]}')

            # Примеры проблем
            if problem_records:
                self.stdout.write(f'\n⚠️ ПРИМЕРЫ ПРОБЛЕМ:')
                for problem in problem_records:
                    self.stdout.write(f'   {problem}')

            # Рекомендации
            self.stdout.write(f'\n💡 РЕКОМЕНДАЦИИ:')
            if empty_tmp_id > 0:
                self.stdout.write(f'   - ✏️ Добавить автогенерацию TMP_ID для записей без ID')
            if empty_name > 0:
                self.stdout.write(f'   - 📝 Добавить дефолтное название для товаров без названия')
            if duplicate_tmp_ids > 0:
                self.stdout.write(f'   - 🔄 Обрабатывать дубликаты TMP_ID (добавлять суффикс)')
            if invalid_chars > 0:
                self.stdout.write(f'   - 🧹 Очищать проблемные символы в данных')
            if empty_producer > 0:
                self.stdout.write(f'   - 🏭 Создавать дефолтный бренд для товаров без производителя')
            if empty_section_id > 0:
                self.stdout.write(f'   - 📁 Создавать дефолтную категорию для товаров без раздела')

            # Прогноз импорта
            self.stdout.write(f'\n🎯 ПРОГНОЗ ИМПОРТА:')
            if lost_records == 0:
                self.stdout.write(self.style.SUCCESS(f'🎉 ВСЕ ЗАПИСИ ВАЛИДНЫ! Должно импортироваться {valid_records} товаров'))
            elif success_rate >= 95:
                self.stdout.write(self.style.SUCCESS(f'✅ ОТЛИЧНЫЙ РЕЗУЛЬТАТ! Будет импортировано {valid_records} из {total_records} товаров ({success_rate:.1f}%)'))
            elif success_rate >= 80:
                self.stdout.write(self.style.WARNING(f'⚠️ ХОРОШИЙ РЕЗУЛЬТАТ. Будет импортировано {valid_records} из {total_records} товаров ({success_rate:.1f}%)'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ МНОГО ПРОБЛЕМ! Будет потеряно {lost_records} товаров из {total_records} ({(100-success_rate):.1f}%)'))

            # Показываем топ производителей и категорий
            if producers:
                sorted_producers = sorted(list(producers))[:10]
                self.stdout.write(f'\n🏭 ТОП ПРОИЗВОДИТЕЛЕЙ (первые 10):')
                for i, producer in enumerate(sorted_producers, 1):
                    self.stdout.write(f'   {i:2d}. {producer}')
            
            if sections:
                sorted_sections = sorted(list(sections))[:10]
                self.stdout.write(f'\n📁 ТОП КАТЕГОРИЙ (первые 10):')
                for i, section in enumerate(sorted_sections, 1):
                    self.stdout.write(f'   {i:2d}. {section}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'💥 Критическая ошибка анализа DBF: {str(e)}'))
            import traceback
            traceback.print_exc()
