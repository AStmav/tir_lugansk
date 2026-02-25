"""
Команда для автоматического связывания изображений товаров
Структура папки images: images/{section_id}/{tmp_id}.jpg
Может быть несколько изображений: {tmp_id}_1.jpg, {tmp_id}_2.jpg и т.д.

Запуск: python manage.py link_product_images
"""
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from shop.models import Product, ProductImage
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Автоматическое связывание изображений с товарами из папки images/'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--images-path',
            type=str,
            default='images',
            help='Путь к папке с изображениями (по умолчанию "images")'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Очистить существующие связи изображений'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Тестовый запуск без сохранения изменений'
        )
    
    def handle(self, *args, **options):
        images_path = options['images_path']
        clear_existing = options['clear_existing']
        dry_run = options['dry_run']
        
        self.stdout.write('🖼️ Начинаем связывание изображений с товарами')
        logger.info("Запуск link_product_images")
        
        if dry_run:
            self.stdout.write('🔬 ТЕСТОВЫЙ РЕЖИМ (без сохранения)')
        
        # Проверка папки
        base_images_path = os.path.join(settings.BASE_DIR, images_path)
        if not os.path.exists(base_images_path):
            error_msg = f'❌ Папка не найдена: {base_images_path}'
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            return
        
        self.stdout.write(f'📁 Папка изображений: {base_images_path}')
        
        # Очистка существующих связей
        if clear_existing:
            if not dry_run:
                deleted_count = ProductImage.objects.count()
                ProductImage.objects.all().delete()
                self.stdout.write(f'🗑️ Удалено {deleted_count} существующих связей')
                logger.info(f"Удалено {deleted_count} связей")
            else:
                self.stdout.write(f'🔬 Будет удалено: {ProductImage.objects.count()} связей')
        
        # Загружаем все товары в кэш
        self.stdout.write('📥 Загружаем товары в кэш...')
        products_by_tmp_id = {}
        for product in Product.objects.only('id', 'tmp_id', 'category__slug').select_related('category'):
            if product.tmp_id:
                products_by_tmp_id[product.tmp_id] = product
        
        self.stdout.write(f'✅ Загружено товаров: {len(products_by_tmp_id)}')
        
        # Статистика
        found_images = 0
        linked_images = 0
        not_found_products = set()
        errors = 0
        
        # Поддерживаемые расширения
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        
        # Обходим папки
        for section_id in os.listdir(base_images_path):
            section_path = os.path.join(base_images_path, section_id)
            
            # Пропускаем файлы
            if not os.path.isdir(section_path):
                continue
            
            self.stdout.write(f'\n📂 Обрабатываем категорию: {section_id}')
            
            for filename in os.listdir(section_path):
                file_path = os.path.join(section_path, filename)
                
                # Пропускаем не-файлы
                if not os.path.isfile(file_path):
                    continue
                
                # Проверяем расширение
                _, ext = os.path.splitext(filename)
                if ext.lower() not in image_extensions:
                    continue
                
                found_images += 1
                
                # Извлекаем tmp_id из имени файла
                # Форматы: {tmp_id}.jpg, {tmp_id}_1.jpg, {tmp_id}_2.jpg
                base_name = os.path.splitext(filename)[0]
                
                # Убираем суффиксы _1, _2 и т.д.
                if '_' in base_name:
                    tmp_id = base_name.rsplit('_', 1)[0]
                else:
                    tmp_id = base_name
                
                # Ищем товар
                product = products_by_tmp_id.get(tmp_id)
                
                if not product:
                    if tmp_id not in not_found_products:
                        if len(not_found_products) < 20:
                            self.stdout.write(f'⚠️ Товар не найден для изображения: {filename} (tmp_id={tmp_id})')
                        not_found_products.add(tmp_id)
                    continue
                
                # Относительный путь для сохранения в БД
                relative_path = os.path.join(images_path, section_id, filename)
                
                # Проверяем размер изображения
                try:
                    with Image.open(file_path) as img:
                        width, height = img.size
                        file_size = os.path.getsize(file_path)
                        
                        if linked_images < 10:
                            self.stdout.write(f'   ✅ {filename} → {product.name} ({width}x{height}, {file_size // 1024}KB)')
                        
                        # Создаем связь
                        if not dry_run:
                            # Проверяем существование через filter (избегаем ошибки при дубликатах)
                            existing = ProductImage.objects.filter(
                                product=product,
                                image=relative_path
                            ).first()
                            
                            if not existing:
                                # Создаем новую связь только если её нет
                                ProductImage.objects.create(
                                    product=product,
                                    image=relative_path,
                                    is_main=linked_images == 0,  # Первое изображение = главное
                                    order=linked_images
                                )
                                linked_images += 1
                            # Если уже существует - пропускаем (не увеличиваем счетчик)
                        else:
                            # В тестовом режиме считаем все
                            linked_images += 1
                
                except Exception as e:
                    errors += 1
                    if errors < 10:
                        self.stdout.write(f'❌ Ошибка обработки {filename}: {e}')
                    logger.error(f"Ошибка обработки {filename}: {e}")
        
        # Финальная статистика
        final_stats = f'''
🎉 СВЯЗЫВАНИЕ ИЗОБРАЖЕНИЙ ЗАВЕРШЕНО!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Статистика:
   • 🖼️ Найдено изображений: {found_images}
   • ✅ Связано с товарами: {linked_images}
   • ⚠️ Товаров не найдено: {len(not_found_products)}
   • ❌ Ошибок обработки: {errors}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'''
        
        self.stdout.write(self.style.SUCCESS(final_stats))
        logger.info(f"Связывание завершено: linked={linked_images}, errors={errors}")
        
        if dry_run:
            self.stdout.write('🔬 Тестовый режим - изменения НЕ сохранены')
        
        # Показываем примеры товаров с изображениями
        if not dry_run and linked_images > 0:
            self.stdout.write('\n📋 Примеры товаров с изображениями:')
            products_with_images = Product.objects.filter(
                images__isnull=False
            ).distinct().prefetch_related('images')[:5]
            
            for product in products_with_images:
                images_count = product.images.count()
                self.stdout.write(f'   • {product.name}: {images_count} изображений')
        
        # Рекомендации
        if len(not_found_products) > 0:
            self.stdout.write(f'\n💡 РЕКОМЕНДАЦИЯ: Сначала импортируйте товары, затем связывайте изображения')
            if len(not_found_products) <= 10:
                self.stdout.write('   Товары не найдены для:')
                for tmp_id in list(not_found_products)[:10]:
                    self.stdout.write(f'      - tmp_id: {tmp_id}')

