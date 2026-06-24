"""
Sitemap: отдача готовых XML с диска (cron) или динамическая генерация (fallback).
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.sitemaps.views import index as django_sitemap_index_view
from django.contrib.sitemaps.views import sitemap as django_sitemap_view
from django.http import HttpResponse
from django.views import View

from shop.sitemap_static import read_static_sitemap, sitemap_section_filename
from shop.sitemaps import SITEMAPS

logger = logging.getLogger(__name__)

_XML_CONTENT_TYPE = "application/xml; charset=utf-8"


def _static_enabled() -> bool:
    return getattr(settings, "SITEMAP_STATIC_ENABLED", True)


def _serve_static(filename: str) -> HttpResponse | None:
    if not _static_enabled():
        return None
    content = read_static_sitemap(filename)
    if content is None:
        return None
    return HttpResponse(content, content_type=_XML_CONTENT_TYPE)


def serve_sitemap_index(request):
    response = _serve_static("sitemap.xml")
    if response is not None:
        return response
    return django_sitemap_index_view(
        request,
        sitemaps=SITEMAPS,
        sitemap_url_name="sitemaps",
    )


def serve_sitemap_section(request, section, page=None):
    if page is None:
        raw_page = request.GET.get("p", 1)
        try:
            page = int(raw_page)
        except (TypeError, ValueError):
            page = 1

    response = _serve_static(sitemap_section_filename(section, page))
    if response is not None:
        return response
    return django_sitemap_view(request, sitemaps=SITEMAPS, section=section)


class RobotsView(View):
    """robots.txt со ссылкой на sitemap index."""

    def get(self, request):
        sitemap_url = request.build_absolute_uri("/sitemap.xml")

        robots_content = f"""User-agent: *
Allow: /

# Запрещаем индексацию админки и служебных страниц
Disallow: /admin/
Disallow: /media/temp/
Disallow: /?search=
Disallow: /*?page=

# Разрешаем индексацию медиа-файлов
Allow: /media/
Allow: /static/

# Sitemap index (дочерние: sitemap-products.xml, sitemap-categories.xml, sitemap-pages.xml)
Sitemap: {sitemap_url}

# Настройки для основных поисковых систем
User-agent: Yandex
Allow: /

User-agent: Googlebot
Allow: /

# Задержка между запросами (в секундах)
Crawl-delay: 1
"""

        logger.info("Robots.txt сгенерирован")
        return HttpResponse(robots_content, content_type="text/plain; charset=utf-8")
