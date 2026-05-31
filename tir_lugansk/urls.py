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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.views.static import serve
import os

# SEO: импорт для sitemap и robots
from shop.views import legacy_supplier_brand_redirect
from shop.sitemap_views import (
    RobotsView,
    SitemapIndexView,
    SitemapSectionView,
)
from shop.feeds import CatalogUpdatesFeed
from pages.views import server_error

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('', include('pages.urls')),
    path('shop/', include('shop.urls')),
    # SEO: редиректы со старого раздела поставщиков
    path(
        'suppliers/',
        RedirectView.as_view(pattern_name='shop:catalog', permanent=True),
    ),
    path('suppliers/<slug:brand_slug>/', legacy_supplier_brand_redirect),
    
    # SEO: sitemap index, дочерние карты и robots
    path('sitemap.xml', SitemapIndexView.as_view(), name='sitemap'),
    path(
        'sitemap-products.xml',
        SitemapSectionView.as_view(),
        {'section': 'products'},
        name='sitemap_products',
    ),
    path(
        'sitemap-categories.xml',
        SitemapSectionView.as_view(),
        {'section': 'categories'},
        name='sitemap_categories',
    ),
    path(
        'sitemap-pages.xml',
        SitemapSectionView.as_view(),
        {'section': 'pages'},
        name='sitemap_pages',
    ),
    path('robots.txt', RobotsView.as_view(), name='robots'),
    path('rss.xml', CatalogUpdatesFeed(), name='rss'),
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

if settings.DEBUG:
    urlpatterns += [
        path('__preview__/500/', server_error, name='preview_500'),
    ]
