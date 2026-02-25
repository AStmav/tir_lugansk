"""
Команда для связывания OE аналогов без товаров с товарами
Запуск: python manage.py link_oe_to_products
"""
from django.core.management.base import BaseCommand
from shop.models import OeKod, Product
import re
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Связывает OE аналоги без товаров с товарами по id_tovar'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без изменений в БД'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write('🔗 Связывание OE аналогов с товарами...')
        logger.info("Начинаем связывание OE аналогов")
        
        # Находим все аналоги без товаров
        analogs_without_product = OeKod.objects.filter(product__isnull=True)
        total = analogs_without_product.count()
        
        self.stdout.write(f'📊 Найдено аналогов без товаров: {total:,}')
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('✅ Все аналоги уже связаны с товарами!'))
            return
        
        # Загружаем все товары в кэш
        self.stdout.write('📥 Загружаем товары в кэш...')
        products_by_tmp_id = {}
        products_by_clean_tmp_id = {}
        
        for product in Product.objects.only('id', 'tmp_id').iterator(chunk_size=5000):
            if product.tmp_id:
                # Сохраняем оригинальный tmp_id
                products_by_tmp_id[product.tmp_id] = product.id
                # Убираем суффикс -dupN для поиска
                clean_tmp_id = re.sub(r'-dup\d+$', '', product.tmp_id)
                if clean_tmp_id != product.tmp_id:
                    products_by_clean_tmp_id[clean_tmp_id] = product.id
        
        self.stdout.write(f'✅ Загружено товаров: {len(products_by_tmp_id):,}')
        
        # Связываем аналоги
        linked_count = 0
        not_found_count = 0
        
        self.stdout.write('🔄 Связываем аналоги...')
        
        for analog in analogs_without_product.iterator(chunk_size=1000):
            if not analog.id_tovar:
                not_found_count += 1
                continue
            
            # Ищем товар по id_tovar (сначала точное совпадение, потом без суффикса)
            product_id = products_by_tmp_id.get(analog.id_tovar)
            
            if not product_id:
                # Пробуем без суффикса -dupN
                clean_id_tovar = re.sub(r'-dup\d+$', '', analog.id_tovar)
                product_id = products_by_clean_tmp_id.get(clean_id_tovar)
            
            if product_id:
                if not dry_run:
                    analog.product_id = product_id
                    analog.save(update_fields=['product_id'])
                linked_count += 1
                
                if linked_count % 1000 == 0:
                    self.stdout.write(f'   Связано: {linked_count:,} / {total:,}')
            else:
                not_found_count += 1
        
        # Результат
        result = f'''
✅ СВЯЗЫВАНИЕ ЗАВЕРШЕНО!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Статистика:
   • Всего аналогов без товаров: {total:,}
   • ✅ Связано с товарами: {linked_count:,}
   • ⚠️ Товар не найден: {not_found_count:,}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'''
        
        if dry_run:
            result += '⚠️ РЕЖИМ ПРОВЕРКИ (dry-run) - изменения НЕ применены\n'
            result += '   Запустите без --dry-run для применения изменений\n'
        
        self.stdout.write(self.style.SUCCESS(result))
        logger.info(f"Связано: {linked_count}, не найдено: {not_found_count}")

