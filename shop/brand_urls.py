"""Канонические URL брендов каталога: /shop/brand/<slug>/"""
from urllib.parse import urlencode

from django.urls import reverse

from .models import Brand


def resolve_active_brand_slug(value):
    """Преобразует slug бренда из query в валидный slug."""
    raw = (value or "").strip()
    if not raw:
        return None
    if Brand.objects.filter(slug=raw).exists():
        return raw
    return None


def brand_canonical_url(brand_slug, query_dict=None):
    """Path страницы бренда с опциональными query (без brand=)."""
    url = reverse("shop:brand", kwargs={"brand_slug": brand_slug})
    if not query_dict:
        return url
    pairs = [(key, val) for key, values in query_dict.lists() if key != "brand" for val in values]
    if not pairs:
        return url
    return f"{url}?{urlencode(pairs, doseq=True)}"


def build_catalog_brand_redirect(request):
    """
    301 с /shop/catalog/?brand=... на /shop/brand/<slug>/,
    если один бренд, нет поиска и нет фильтра по категории.
    """
    if (request.GET.get("search") or "").strip():
        return None

    if request.GET.getlist("category"):
        return None

    brand_values = request.GET.getlist("brand")
    if len(brand_values) != 1:
        return None

    slug = resolve_active_brand_slug(brand_values[0])
    if not slug:
        return None

    return brand_canonical_url(slug, request.GET)
