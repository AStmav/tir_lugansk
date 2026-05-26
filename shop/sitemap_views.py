"""
Представления для sitemap index, дочерних sitemap и robots.txt.
"""
import logging
from xml.sax.saxutils import escape

from django.http import Http404, HttpResponse
from django.views import View

from .seo import (
    SITEMAP_SECTIONS,
    _sitemap_section_lastmod,
    generate_sitemap_urls,
    get_sitemap_section_urls,
)

logger = logging.getLogger(__name__)

SITEMAP_URL_LIMIT = 50000


def _format_lastmod(value):
    if value and hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return None


def _render_urlset(request, urls):
    if len(urls) > SITEMAP_URL_LIMIT:
        logger.warning(
            "Sitemap обрезан: %s URL (лимит %s)",
            len(urls),
            SITEMAP_URL_LIMIT,
        )
        urls = urls[:SITEMAP_URL_LIMIT]

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for url_data in urls:
        loc = escape(request.build_absolute_uri(url_data["loc"]))
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")

        lastmod = _format_lastmod(url_data.get("lastmod"))
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")

        lines.append(f"    <changefreq>{url_data['changefreq']}</changefreq>")
        lines.append(f"    <priority>{url_data['priority']}</priority>")
        lines.append("  </url>")

    lines.append("</urlset>")
    return "\n".join(lines)


class SitemapIndexView(View):
    """Корневой /sitemap.xml — индекс дочерних карт."""

    def get(self, request):
        try:
            lines = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            ]

            for section_key, path, _generator_name in SITEMAP_SECTIONS:
                entries = get_sitemap_section_urls(section_key) or []
                lastmod = _format_lastmod(_sitemap_section_lastmod(entries))

                loc = escape(request.build_absolute_uri(path))
                lines.append("  <sitemap>")
                lines.append(f"    <loc>{loc}</loc>")
                if lastmod:
                    lines.append(f"    <lastmod>{lastmod}</lastmod>")
                lines.append("  </sitemap>")

            lines.append("</sitemapindex>")
            xml_content = "\n".join(lines)

            logger.info("Sitemap index сгенерирован: %s частей", len(SITEMAP_SECTIONS))
            return HttpResponse(xml_content, content_type="application/xml; charset=utf-8")

        except Exception as exc:
            logger.exception("Ошибка генерации sitemap index: %s", exc)
            return HttpResponse("Ошибка генерации sitemap", status=500)


class SitemapSectionView(View):
    """Дочерние карты: products, categories, pages."""

    def get(self, request, section):
        try:
            urls = get_sitemap_section_urls(section)
            if urls is None:
                raise Http404(f"Unknown sitemap section: {section}")

            xml_content = _render_urlset(request, urls)
            logger.info("Sitemap-%s: %s URL", section, len(urls))
            return HttpResponse(xml_content, content_type="application/xml; charset=utf-8")

        except Http404:
            raise
        except Exception as exc:
            logger.exception("Ошибка генерации sitemap-%s: %s", section, exc)
            return HttpResponse("Ошибка генерации sitemap", status=500)


class SitemapView(View):
    """
    Устаревший единый sitemap (все URL в одном файле).
    Оставлен для обратной совместимости; в robots указан индекс /sitemap.xml.
    """

    def get(self, request):
        try:
            urls = generate_sitemap_urls()
            xml_content = _render_urlset(request, urls)
            logger.info("Sitemap (full): %s URL", len(urls))
            return HttpResponse(xml_content, content_type="application/xml; charset=utf-8")
        except Exception as exc:
            logger.exception("Ошибка генерации полного sitemap: %s", exc)
            return HttpResponse("Ошибка генерации sitemap", status=500)


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
