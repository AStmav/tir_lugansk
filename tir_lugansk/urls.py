"""
URL configuration for tir_lugansk project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.views.static import serve
import os

# SEO: импорт для sitemap и robots
from shop.views import legacy_supplier_brand_redirect, legacy_suppliers_letter_redirect
from shop.legacy_redirects import (
    legacy_assortment_redirect,
    legacy_company_redirect,
    legacy_information_redirect,
)
from shop.sitemap_views import RobotsView, serve_sitemap_index, serve_sitemap_section
from shop.feeds import CatalogUpdatesFeed
from pages.views import server_error

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('shop/', include('shop.urls')),
    # SEO: редиректы со старого раздела поставщиков
    path(
        'suppliers/',
        RedirectView.as_view(pattern_name='shop:brands', permanent=True),
    ),
    path('suppliers/letter-<str:letter>/', legacy_suppliers_letter_redirect),
    path('suppliers/<slug:brand_slug>/', legacy_supplier_brand_redirect),
    # SEO: редиректы со старой структуры сайта
    re_path(r'^assortment(?:/(?P<path>.*))?$', legacy_assortment_redirect),
    re_path(r'^information(?:/(?P<path>.*))?$', legacy_information_redirect),
    path('company/', legacy_company_redirect),
    # SEO: sitemap index, дочерние карты и robots (до catch-all в pages.urls)
    path('sitemap.xml', serve_sitemap_index, name='sitemap'),
    path(
        'sitemap-<section>-p<int:page>.xml',
        serve_sitemap_section,
        name='sitemaps_paged',
    ),
    path(
        'sitemap-<section>.xml',
        serve_sitemap_section,
        name='sitemaps',
    ),
    path('robots.txt', RobotsView.as_view(), name='robots'),
    path('rss.xml', CatalogUpdatesFeed(), name='rss'),
    path('', include('pages.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Добавляем обслуживание статических файлов для продакшн
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Добавляем обслуживание изображений из папки images
if settings.DEBUG:
    urlpatterns += [
        path('images/<path:path>', serve, {
            'document_root': os.path.join(settings.BASE_DIR, 'images'),
        }),
    ]
else:
    # В продакшн режиме тоже добавляем раздачу изображений
    urlpatterns += [
        path('images/<path:path>', serve, {
            'document_root': os.path.join(settings.BASE_DIR, 'images'),
        }),
    ]

handler500 = 'pages.views.server_error'
handler404 = 'pages.views.page_not_found'

if settings.DEBUG:
    urlpatterns += [
        path('__preview__/500/', server_error, name='preview_500'),
    ]
