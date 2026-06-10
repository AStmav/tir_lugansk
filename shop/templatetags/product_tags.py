"""Теги для карточек товаров."""
import json

from django import template
from django.utils.html import escape

register = template.Library()


@register.filter
def lightbox_images_json(urls):
    """JSON-массив URL для атрибута data-lightbox-images."""
    if not urls:
        return ""
    return escape(json.dumps(list(urls), ensure_ascii=False))
