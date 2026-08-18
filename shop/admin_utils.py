"""Ссылки на карточку товара в админке и на сайте."""
from django.urls import reverse
from django.utils.html import format_html


def product_short_label(product) -> str:
    """Краткая подпись: бренд · кат.номер · название."""
    if not product:
        return '—'
    parts = []
    brand = getattr(product, 'brand', None)
    if brand:
        parts.append((brand.name or brand.code or '').strip())
    catalog = (product.catalog_number or '').strip()
    if catalog:
        parts.append(catalog)
    elif (product.code or '').strip():
        parts.append(product.code.strip())
    name = (product.name or '').strip()
    if name:
        parts.append(name[:80] + ('…' if len(name) > 80 else ''))
    label = ' · '.join(p for p in parts if p)
    return label or f'#{product.pk}'


def product_nav_links(product):
    """HTML: подпись + ссылки «Админ» и «Сайт»."""
    if not product or not product.pk:
        return '—'
    admin_url = reverse('admin:shop_product_change', args=[product.pk])
    site_url = product.get_absolute_url()
    return format_html(
        '<div style="line-height:1.35;">'
        '<div>{}</div>'
        '<a href="{}">Админ</a> · '
        '<a href="{}" target="_blank" rel="noopener">Сайт</a>'
        '</div>',
        product_short_label(product),
        admin_url,
        site_url,
    )
