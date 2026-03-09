"""
Template tags для SEO оптимизации
"""
from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()


@register.simple_tag(takes_context=True)
def render_breadcrumbs(context, product=None, category=None):
    """
    Генерация хлебных крошек (breadcrumbs) с Schema.org разметкой
    """
    request = context['request']
    items = [
        {'name': 'Главная', 'url': '/'}
    ]
    
    # Добавляем каталог
    items.append({'name': 'Каталог', 'url': '/catalog/'})
    
    # Если есть категория
    if category:
        items.append({'name': category.name, 'url': category.get_absolute_url()})
    elif product and product.category:
        items.append({'name': product.category.name, 'url': product.category.get_absolute_url()})
    
    # Если есть товар
    if product:
        items.append({'name': product.name, 'url': product.get_absolute_url()})
    
    # Генерируем HTML
    html = '<nav aria-label="breadcrumb"><ol class="breadcrumb">'
    
    for i, item in enumerate(items):
        is_last = (i == len(items) - 1)
        
        if is_last:
            html += f'<li class="breadcrumb-item active" aria-current="page">{item["name"]}</li>'
        else:
            html += f'<li class="breadcrumb-item"><a href="{item["url"]}">{item["name"]}</a></li>'
    
    html += '</ol></nav>'
    
    # Добавляем Schema.org разметку
    schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": []
    }
    
    for i, item in enumerate(items):
        schema["itemListElement"].append({
            "@type": "ListItem",
            "position": i + 1,
            "name": item["name"],
            "item": request.build_absolute_uri(item["url"])
        })
    
    html += f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>'
    
    return mark_safe(html)


@register.simple_tag
def render_structured_data(data):
    """
    Вывод структурированных данных (Schema.org) в формате JSON-LD
    """
    if not data:
        return ''
    
    json_data = json.dumps(data, ensure_ascii=False, indent=2)
    html = f'<script type="application/ld+json">{json_data}</script>'
    
    return mark_safe(html)


@register.simple_tag(takes_context=True)
def render_meta_tags(context):
    """
    Вывод всех SEO meta-тегов
    """
    seo = context.get('seo', {})
    
    html = []
    
    # Основные meta-теги
    if seo.get('title'):
        html.append(f'<title>{seo["title"]}</title>')
        html.append(f'<meta property="og:title" content="{seo["title"]}">')
        html.append(f'<meta name="twitter:title" content="{seo["title"]}">')
    
    if seo.get('description'):
        html.append(f'<meta name="description" content="{seo["description"]}">')
        html.append(f'<meta property="og:description" content="{seo["description"]}">')
        html.append(f'<meta name="twitter:description" content="{seo["description"]}">')
    
    if seo.get('keywords'):
        html.append(f'<meta name="keywords" content="{seo["keywords"]}">')
    
    # Canonical URL
    if seo.get('canonical_url'):
        html.append(f'<link rel="canonical" href="{seo["canonical_url"]}">')
        html.append(f'<meta property="og:url" content="{seo["canonical_url"]}">')
    
    # Open Graph
    if seo.get('og_type'):
        html.append(f'<meta property="og:type" content="{seo["og_type"]}">')
    
    if seo.get('og_image'):
        html.append(f'<meta property="og:image" content="{seo["og_image"]}">')
        html.append(f'<meta name="twitter:image" content="{seo["og_image"]}">')
    
    html.append('<meta property="og:site_name" content="TIR-Lugansk">')
    
    # Twitter Card
    if seo.get('twitter_card'):
        html.append(f'<meta name="twitter:card" content="{seo["twitter_card"]}">')
    
    # Viewport и другие технические теги
    html.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html.append('<meta charset="utf-8">')
    
    return mark_safe('\n'.join(html))


@register.filter
def truncate_description(text, length=160):
    """
    Обрезка текста для meta-description (оптимальная длина 150-160 символов)
    """
    if not text:
        return ''
    
    if len(text) <= length:
        return text
    
    # Обрезаем по словам
    truncated = text[:length].rsplit(' ', 1)[0]
    return f"{truncated}..."


@register.filter
def price_space(value):
    """
    Цена с пробелом как разделителем тысяч: 1400 → "1 400" (как на макете заказчика).
    """
    if value is None:
        return ''
    try:
        num = int(float(value))
        return f'{num:,}'.replace(',', ' ')
    except (ValueError, TypeError):
        return str(value)

