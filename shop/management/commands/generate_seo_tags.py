"""
Команда для генерации SEO тегов для всех товаров без них
Запуск: python manage.py generate_seo_tags
"""
from django.core.management.base import BaseCommand
from shop.models import Product
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Генерирует SEO теги (meta_title, meta_description, meta_keywords) для товаров без них'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Перегенерировать SEO теги даже если они уже есть'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Размер пачки для обновления (по умолчанию 1000)'
        )
    
    def handle(self, *args, **options):
        force = options['force']
        batch_size = options['batch_size']
        
        self.stdout.write('🔄 Начинаем генерацию SEO тегов...')
        
        # Выбираем товары для обновления
        if force:
            products = Product.objects.select_related('brand', 'category').all()
            self.stdout.write(f'📊 Режим: FORCE - обновляем все товары')
        else:
            products = Product.objects.select_related('brand', 'category').filter(
                meta_title='',
                meta_description='',
                meta_keywords=''
            )
            self.stdout.write(f'📊 Режим: только товары без SEO тегов')
        
        total = products.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('✅ Все товары уже имеют SEO теги!'))
            return
        
        self.stdout.write(f'📊 Всего товаров для обновления: {total}')
        
        updated_count = 0
        batch = []
        
        for i, product in enumerate(products, 1):
            # Очищаем SEO поля чтобы триггернуть автогенерацию
            product.meta_title = ''
            product.meta_description = ''
            product.meta_keywords = ''
            
            # save() автоматически сгенерирует SEO теги
            product.save()
            updated_count += 1
            
            if i % 100 == 0:
                progress = (i / total) * 100
                self.stdout.write(f'⏳ Прогресс: {progress:.1f}% ({i}/{total})')
                logger.info(f'Сгенерировано SEO для {i} товаров')
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Готово! Сгенерировано SEO для {updated_count} товаров'))
        
        # Показываем примеры
        self.stdout.write('\n📋 Примеры сгенерированных SEO тегов:')
        sample_products = Product.objects.filter(
            meta_title__isnull=False
        ).exclude(meta_title='')[:3]
        
        for product in sample_products:
            self.stdout.write(f'\n🔹 {product.name[:50]}')
            self.stdout.write(f'   Title: {product.meta_title[:80]}...')
            self.stdout.write(f'   Desc:  {product.meta_description[:80]}...')
        
        self.stdout.write('\n💡 РЕКОМЕНДАЦИИ:')
        self.stdout.write('─' * 60)
        self.stdout.write('1. Проверьте SEO теги в админке и отредактируйте при необходимости')
        self.stdout.write('2. Используйте инструменты проверки SEO (Google Search Console)')
        self.stdout.write('3. Регулярно обновляйте мета-описания для лучшего ранжирования')
        self.stdout.write('4. Sitemap доступен по адресу: /sitemap.xml')
        self.stdout.write('5. Robots.txt доступен по адресу: /robots.txt')

