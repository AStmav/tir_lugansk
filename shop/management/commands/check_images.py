import os
from django.core.management.base import BaseCommand
from django.conf import settings
from shop.models import Product


class Command(BaseCommand):
    help = 'Проверка покрытия товаров изображениями'

    def handle(self, *args, **options):
        self.stdout.write('📊 Анализ изображений товаров...')
        
        # Получаем все товары
        all_products = Product.objects.all()
        total_products = all_products.count()
        
        # Считаем товары с изображениями
        products_with_images = 0
        products_without_images = 0
        missing_images = []
        
        for product in all_products:
            if product.has_main_image:
                products_with_images += 1
            else:
                products_without_images += 1
                if len(missing_images) < 10:  # Показываем только первые 10
                    missing_images.append({
                        'code': product.code,
                        'name': product.name[:50],
                        'category': product.category.slug if product.category else 'None'
                    })
        
        # Статистика
        coverage_percent = (products_with_images / total_products * 100) if total_products > 0 else 0
        
        self.stdout.write(f'\n📈 СТАТИСТИКА ИЗОБРАЖЕНИЙ:')
        self.stdout.write(f'📦 Всего товаров: {total_products}')
        self.stdout.write(f'🖼️ С изображениями: {products_with_images}')
        self.stdout.write(f'❌ Без изображений: {products_without_images}')
        self.stdout.write(f'📊 Покрытие: {coverage_percent:.1f}%')
        
        if coverage_percent >= 80:
            self.stdout.write(self.style.SUCCESS('🎉 ОТЛИЧНОЕ покрытие изображениями!'))
        elif coverage_percent >= 60:
            self.stdout.write(self.style.WARNING('⚠️ ХОРОШЕЕ покрытие, но можно улучшить'))
        elif coverage_percent >= 40:
            self.stdout.write(self.style.WARNING('📸 СРЕДНЕЕ покрытие - нужно больше изображений'))
        else:
            self.stdout.write(self.style.ERROR('❗ НИЗКОЕ покрытие - критично мало изображений'))
        
        # Показываем примеры товаров без изображений
        if missing_images:
            self.stdout.write(f'\n❌ ПРИМЕРЫ ТОВАРОВ БЕЗ ИЗОБРАЖЕНИЙ:')
            for item in missing_images:
                self.stdout.write(f'  • {item["code"]} | {item["name"]} | {item["category"]}')
            
            if products_without_images > 10:
                self.stdout.write(f'  ... и еще {products_without_images - 10} товаров')
        
        # Проверяем физические файлы
        images_path = os.path.join(settings.BASE_DIR, 'images')
        if os.path.exists(images_path):
            total_image_files = 0
            for root, dirs, files in os.walk(images_path):
                total_image_files += len([f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
            
            self.stdout.write(f'\n📁 ФАЙЛОВАЯ СИСТЕМА:')
            self.stdout.write(f'🖼️ Всего файлов изображений: {total_image_files}')
            
            if total_image_files > products_with_images:
                orphaned = total_image_files - products_with_images
                self.stdout.write(f'👻 Лишних файлов (без товаров): ~{orphaned}')
        
        self.stdout.write(f'\n💡 РЕКОМЕНДАЦИИ:')
        if coverage_percent < 60:
            self.stdout.write('• Добавить больше изображений товаров')
            self.stdout.write('• Проверить соответствие имен файлов кодам товаров')
        if coverage_percent > 90:
            self.stdout.write('• Отличная работа! Почти все товары с изображениями')
        else:
            self.stdout.write('• Продолжить пополнение базы изображений')
            self.stdout.write('• Возможно, стоит оптимизировать существующие изображения') 