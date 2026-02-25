"""
Команда для импорта брендов из DBF файла Brends.dbf
Структура файла:
- ID_BRENB (основное поле): Уникальный ID производителя
- NAME: Наименование бренда

Поддерживаются альтернативные названия: ID_BREND, ID_brend, ID_brand и др.
Запуск: python manage.py import_brands_dbf Brends.dbf
"""
import os
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from shop.models import Brand, ImportFile
from django.utils import timezone
import logging

try:
    from dbfread import DBF
except ImportError:
    DBF = None

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Импорт брендов (производителей) из DBF файла Brends.dbf (~2,800 записей)'
    
    def add_arguments(self, parser):
        parser.add_argument('dbf_file', type=str, help='Путь к DBF файлу с брендами (Brends.dbf)')
        parser.add_argument('--encoding', type=str, default='cp1251', help='Кодировка DBF файла (по умолчанию cp1251)')
        parser.add_argument('--clear-existing', action='store_true', help='Очистить существующие бренды перед импортом')
        parser.add_argument('--import-file-id', type=int, help='ID записи ImportFile для отслеживания прогресса')
        parser.add_argument('--test-records', type=int, default=0, help='Ограничить импорт первыми N записями (для тестирования)')
    
    def handle(self, *args, **options):
        if not DBF:
            error_msg = '❌ Библиотека dbfread не установлена! Выполните: pip install dbfread'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            return
        
        dbf_file = options['dbf_file']
        encoding = options['encoding']
        clear_existing = options['clear_existing']
        import_file_id = options.get('import_file_id')
        test_records = options.get('test_records', 0)
        import_file = None
        
        self.stdout.write(f'🔄 Начинаем импорт брендов из DBF файла: {dbf_file}')
        logger.info(f"Начинаем импорт брендов из: {dbf_file}")
        
        # Настройка ImportFile для отслеживания прогресса
        if import_file_id:
            import_file = ImportFile.objects.filter(id=import_file_id).first()
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(
                    status='processing',
                    error_log='',
                    current_row=0,
                    created_products=0,
                    updated_products=0,
                    error_count=0,
                )
        
        # Проверяем существование файла
        if not os.path.exists(dbf_file):
            error_msg = f'❌ DBF файл не найден: {dbf_file}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)
            return
        
        # Проверяем расширение файла
        if not dbf_file.lower().endswith('.dbf'):
            error_msg = f'❌ Файл должен иметь расширение .dbf: {dbf_file}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)
            return
        
        # Очищаем существующие бренды если указан флаг
        if clear_existing:
            self.stdout.write('🗑️ Очищаем существующие бренды...')
            deleted_count = Brand.objects.count()
            Brand.objects.all().delete()
            self.stdout.write(f'✅ Удалено {deleted_count} существующих брендов')
            logger.info(f"Удалено {deleted_count} существующих брендов")
        
        # Открываем DBF файл
        try:
            table = DBF(dbf_file, encoding=encoding)
            total_records = len(table)
            
            self.stdout.write(f'📊 Всего записей в DBF файле: {total_records}')
            logger.info(f"Всего записей в DBF файле: {total_records}")
            
            if test_records > 0:
                self.stdout.write(f'🔬 Тестовый режим: обработаем только {test_records} записей')
            
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(total_rows=total_records)
                
        except Exception as e:
            error_msg = f'❌ Ошибка открытия DBF файла: {str(e)}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            if import_file:
                ImportFile.objects.filter(id=import_file.id).update(status='failed', error_log=error_msg)
            return
        
        # Показываем структуру первой записи для отладки
        try:
            first_record = next(iter(table))
            self.stdout.write('🔍 Структура DBF файла:')
            for key, value in first_record.items():
                self.stdout.write(f'   {key}: {value} ({type(value).__name__})')
            logger.info(f"Структура DBF: {list(first_record.keys())}")
        except Exception as e:
            self.stdout.write(f'⚠️ Не удалось прочитать первую запись: {e}')
        
        # Статистика
        created_count = 0
        updated_count = 0
        errors = 0
        skipped_count = 0
        
        # Основной цикл импорта
        for record_num, record in enumerate(table, start=1):
            try:
                # Ограничение для тестирования
                if test_records > 0 and record_num > test_records:
                    self.stdout.write(f'🔬 Достигнут лимит тестовых записей: {test_records}')
                    break
                
                # Извлекаем поля из записи (пробуем разные варианты названий)
                id_brend = str(
                    record.get('ID_BRENB', '') or 
                    record.get('ID_brenb', '') or 
                    record.get('ID_BREND', '') or 
                    record.get('ID_brend', '') or 
                    record.get('ID_brand', '')
                ).strip()
                name = str(record.get('NAME', '') or record.get('Name', '')).strip()
                
                # Логируем первые записи
                if record_num <= 5:
                    self.stdout.write(f'🔍 Запись {record_num}: ID_BRENB="{id_brend}", NAME="{name}"')
                    logger.info(f"Запись {record_num}: ID_BRENB={id_brend}, NAME={name}")
                
                # Валидация обязательных полей
                if not id_brend or not name:
                    skipped_count += 1
                    if skipped_count <= 10:
                        self.stdout.write(f'⚠️ Пропуск записи {record_num}: пустые обязательные поля (ID_BRENB="{id_brend}", NAME="{name}")')
                    continue
                
                # Пропускаем служебные записи (заголовки таблицы)
                if id_brend.lower() in ['id_brend', 'code', 'character'] or name.lower() in ['name', 'character']:
                    skipped_count += 1
                    continue
                
                # Создаем slug для URL
                # Используем ID_BRENB для slug, чтобы избежать конфликтов
                brand_slug = slugify(f'{id_brend}-{name}')[:50]  # Ограничиваем длину
                
                # Если slug слишком короткий, используем только ID
                if len(brand_slug) < 3:
                    brand_slug = f'brand-{id_brend}'
                
                # Создаем или обновляем бренд
                brand, created = Brand.objects.update_or_create(
                    code=id_brend,  # Уникальный идентификатор из 1С
                    defaults={
                        'slug': brand_slug,
                        'name': name,
                        'description': f'Производитель автозапчастей (ID: {id_brend})'
                    }
                )
                
                if created:
                    created_count += 1
                    if created_count <= 10:
                        self.stdout.write(f'✅ Создан бренд: {name} (ID: {id_brend})')
                    logger.info(f"Создан бренд: {name} (ID: {id_brend})")
                else:
                    updated_count += 1
                    if updated_count <= 10:
                        self.stdout.write(f'🔄 Обновлен бренд: {name} (ID: {id_brend})')
                
                # Обновляем прогресс каждые 100 записей
                if record_num % 100 == 0:
                    progress = (record_num / total_records) * 100
                    self.stdout.write(f'⏳ Прогресс: {progress:.1f}% ({record_num}/{total_records}) | Создано: {created_count}, Обновлено: {updated_count}')
                    
                    if import_file:
                        ImportFile.objects.filter(id=import_file.id).update(
                            current_row=record_num,
                            created_products=created_count,
                            updated_products=updated_count,
                            error_count=errors
                        )
            
            except Exception as e:
                errors += 1
                if errors <= 10:
                    error_msg = f'❌ Ошибка в записи {record_num}: {str(e)}'
                    self.stdout.write(self.style.ERROR(error_msg))
                    logger.error(error_msg)
                
                if import_file:
                    ImportFile.objects.filter(id=import_file.id).update(error_count=errors)
                continue
        
        # Финальная статистика
        total_brands = Brand.objects.count()
        
        final_stats = f'''
🎉 ИМПОРТ БРЕНДОВ ЗАВЕРШЕН!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Статистика:
   • Обработано записей: {record_num}
   • ✅ Создано брендов: {created_count}
   • 🔄 Обновлено брендов: {updated_count}
   • ⏭️ Пропущено записей: {skipped_count}
   • ❌ Ошибок: {errors}
   • 📦 Всего брендов в базе: {total_brands}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'''
        
        self.stdout.write(self.style.SUCCESS(final_stats))
        logger.info(f"Импорт завершен: создано={created_count}, обновлено={updated_count}, ошибок={errors}")
        
        # Показываем примеры импортированных брендов
        self.stdout.write('📋 Примеры импортированных брендов:')
        sample_brands = Brand.objects.order_by('-id')[:10]
        for brand in sample_brands:
            self.stdout.write(f'   • {brand.name} (код: {brand.code})')
        
        # Обновляем статус ImportFile
        if import_file:
            ImportFile.objects.filter(id=import_file.id).update(
                processed=True,
                processed_at=timezone.now(),
                status='completed',
                current_row=record_num,
                created_products=created_count,
                updated_products=updated_count,
                error_count=errors
            )

