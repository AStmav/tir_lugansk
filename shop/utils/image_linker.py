"""
Утилита для связывания изображений с товарами
Структура: images/{section_id}/{tmp_id}.jpg
"""
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def link_images_for_products(queryset):
    """
    Связывает изображения с товарами из queryset.
    ОПТИМИЗИРОВАНО: Сначала индексирует все файлы, потом быстро ищет.
    
    Args:
        queryset: QuerySet товаров (Product)
    
    Returns:
        tuple: (количество_связанных, всего_товаров)
    """
    from shop.models import ProductImage
    import re
    
    images_dir = os.path.join(settings.BASE_DIR, 'images')
    
    if not os.path.exists(images_dir):
        logger.error(f"Папка {images_dir} не существует")
        return 0, queryset.count()
    
    total_count = queryset.count()
    logger.info(f"Начинаем связывание изображений для {total_count} товаров")
    
    # ШАГ 1: ИНДЕКСАЦИЯ - читаем все файлы в словарь (1 раз, быстро!)
    logger.info("Шаг 1/2: Индексация файлов изображений...")
    image_files = {}  # {tmp_id: [(section_dir, filename), ...]}
    
    for section_dir in os.listdir(images_dir):
        section_path = os.path.join(images_dir, section_dir)
        
        if not os.path.isdir(section_path):
            continue
        
        for filename in os.listdir(section_path):
            # Только изображения
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            # Извлекаем tmp_id из имени файла (без расширения)
            tmp_id = os.path.splitext(filename)[0]
            
            if tmp_id not in image_files:
                image_files[tmp_id] = []
            
            image_files[tmp_id].append((section_dir, filename))
    
    logger.info(f"Проиндексировано {len(image_files)} уникальных изображений")
    
    # ШАГ 2: СВЯЗЫВАНИЕ - быстрый поиск в словаре
    logger.info("Шаг 2/2: Связывание изображений с товарами...")
    linked_count = 0
    batch = []
    batch_size = 1000
    processed = 0
    
    for product in queryset.iterator(chunk_size=1000):
        processed += 1
        
        if not product.tmp_id:
            continue
        
        # Убираем суффикс -dupN если есть
        clean_tmp_id = re.sub(r'-dup\d+$', '', product.tmp_id)
        
        # Быстрый поиск в словаре (вместо перебора папок!)
        if clean_tmp_id in image_files:
            for section_dir, filename in image_files[clean_tmp_id]:
                relative_path = os.path.join('images', section_dir, filename)
                
                batch.append(ProductImage(
                    product=product,
                    image=relative_path,
                    is_main=(linked_count == 0)  # Только самое первое главное
                ))
                linked_count += 1
        
        # Сохраняем батч
        if len(batch) >= batch_size:
            ProductImage.objects.bulk_create(batch, ignore_conflicts=True)
            logger.info(f"Обработано {processed}/{total_count} товаров, создано {linked_count} связей")
            batch = []
    
    # Сохраняем остаток
    if batch:
        ProductImage.objects.bulk_create(batch, ignore_conflicts=True)
    
    logger.info(f"✅ Связывание завершено: {linked_count} изображений для {total_count} товаров")
    
    return linked_count, total_count

