"""
Сигналы для инвалидации кеша при изменении данных
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Category, Brand
import logging

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_cache(sender, instance, **kwargs):
    """
    Сбрасываем кеш категорий при любых изменениях
    """
    cache.delete('main_categories')
    cache.delete('all_categories')
    logger.info(f'Кеш категорий инвалидирован после изменения: {instance}')


@receiver([post_save, post_delete], sender=Brand)
def invalidate_brand_cache(sender, instance, **kwargs):
    """
    Сбрасываем кеш брендов при любых изменениях
    """
    cache.delete('all_brands')
    logger.info(f'Кеш брендов инвалидирован после изменения: {instance}')

