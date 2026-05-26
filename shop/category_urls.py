"""Канонические URL категорий каталога: /shop/category/<slug>/"""
from urllib.parse import urlencode

from django.shortcuts import get_object_or_404
from django.urls import reverse

from .models import Category


def resolve_active_category_slug(value):
    """Преобразует slug или id из query в slug активной категории."""
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        category = Category.objects.filter(id=int(raw), is_active=True).only("slug").first()
        return category.slug if category else None
    if Category.objects.filter(slug=raw, is_active=True).exists():
        return raw
    return None


def category_canonical_url(category_slug, query_dict=None):
    """Абсолютный path категории с опциональными query-параметрами (без category=)."""
    url = reverse("shop:category", kwargs={"category_slug": category_slug})
    if not query_dict:
        return url
    pairs = [(key, val) for key, values in query_dict.lists() if key != "category" for val in values]
    if not pairs:
        return url
    return f"{url}?{urlencode(pairs, doseq=True)}"


def build_catalog_category_redirect(request):
    """
    301 с /shop/catalog/?category=... на /shop/category/<slug>/,
    если в query ровно одна категория и нет поиска.
    """
    if (request.GET.get("search") or "").strip():
        return None

    category_values = request.GET.getlist("category")
    if len(category_values) != 1:
        return None

    slug = resolve_active_category_slug(category_values[0])
    if not slug:
        return None

    return category_canonical_url(slug, request.GET)
