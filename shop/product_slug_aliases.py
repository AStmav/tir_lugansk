"""Разрешение slug товара: канонический URL и 301 со старых алиасов."""
from .models import Product, ProductSlugAlias


def resolve_product_with_legacy(slug):
    """
    Возвращает (product, needs_redirect).
    needs_redirect=True — запрос пришёл по старому slug из ProductSlugAlias.
    """
    raw = (slug or '').strip()
    if not raw:
        return None, False

    product = Product.objects.filter(slug=raw).first()
    if product:
        return product, False

    alias = (
        ProductSlugAlias.objects.filter(slug=raw)
        .select_related('product')
        .first()
    )
    if alias:
        return alias.product, True

    return None, False
