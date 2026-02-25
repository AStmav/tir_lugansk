"""
Представления для генерации sitemap.xml и robots.txt
"""
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views import View
from .seo import generate_sitemap_urls
import logging

logger = logging.getLogger(__name__)


class SitemapView(View):
    """
    Генерация XML sitemap для поисковых систем
    """
    
    def get(self, request):
        try:
            urls = generate_sitemap_urls()
            
            # Генерируем XML
            xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            
            for url_data in urls:
                xml_content += '  <url>\n'
                xml_content += f'    <loc>{request.build_absolute_uri(url_data["loc"])}</loc>\n'
                
                if url_data.get('lastmod'):
                    xml_content += f'    <lastmod>{url_data["lastmod"].strftime("%Y-%m-%d")}</lastmod>\n'
                
                xml_content += f'    <changefreq>{url_data["changefreq"]}</changefreq>\n'
                xml_content += f'    <priority>{url_data["priority"]}</priority>\n'
                xml_content += '  </url>\n'
            
            xml_content += '</urlset>'
            
            logger.info(f"Sitemap сгенерирован: {len(urls)} URL")
            
            return HttpResponse(xml_content, content_type='application/xml')
        
        except Exception as e:
            logger.error(f"Ошибка генерации sitemap: {e}")
            return HttpResponse('Ошибка генерации sitemap', status=500)


class RobotsView(View):
    """
    Генерация robots.txt
    """
    
    def get(self, request):
        sitemap_url = request.build_absolute_uri('/sitemap.xml')
        
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
        
        return HttpResponse(robots_content, content_type='text/plain')

