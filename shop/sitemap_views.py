"""
Представления для генерации sitemap.xml и robots.txt
"""
import logging
from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.views import View

from .seo import generate_sitemap_urls

logger = logging.getLogger(__name__)

SITEMAP_URL_LIMIT = 50000


class SitemapView(View):
    """Динамический XML sitemap для поисковых систем."""

    def get(self, request):
        try:
            urls = generate_sitemap_urls()
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

                lastmod = url_data.get("lastmod")
                if lastmod:
                    if hasattr(lastmod, "strftime"):
                        lines.append(f"    <lastmod>{lastmod.strftime('%Y-%m-%d')}</lastmod>")

                lines.append(f"    <changefreq>{url_data['changefreq']}</changefreq>")
                lines.append(f"    <priority>{url_data['priority']}</priority>")
                lines.append("  </url>")

            lines.append("</urlset>")
            xml_content = "\n".join(lines)

            logger.info("Sitemap сгенерирован: %s URL", len(urls))
            return HttpResponse(xml_content, content_type="application/xml; charset=utf-8")

        except Exception as exc:
            logger.exception("Ошибка генерации sitemap: %s", exc)
            return HttpResponse("Ошибка генерации sitemap", status=500)


class RobotsView(View):
    """robots.txt со ссылкой на sitemap."""

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

# Ссылка на sitemap
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
