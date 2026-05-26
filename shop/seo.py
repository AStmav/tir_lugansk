"""
SEO утилиты и миксины для оптимизации сайта под поисковые системы
"""
from django.conf import settings
from django.urls import reverse


class SEOMixin:
    """
    Миксин для добавления SEO-данных в контекст
    """
    
    def get_seo_title(self):
        """Генерация SEO-заголовка"""
        return getattr(self, 'seo_title', 'Автозапчасти TIR-Lugansk')
    
    def get_seo_description(self):
        """Генерация SEO-описания"""
        return getattr(self, 'seo_description', 
                      'Интернет-магазин автозапчастей в Луганске. Широкий ассортимент запчастей от проверенных производителей.')
    
    def get_seo_keywords(self):
        """Генерация SEO-ключевых слов"""
        return getattr(self, 'seo_keywords', 
                      'автозапчасти, запчасти Луганск, автомагазин, автодетали')
    
    def get_og_image(self):
        """Open Graph изображение"""
        return getattr(self, 'og_image', f"{settings.STATIC_URL}images/og-default.jpg")
    
    def get_canonical_url(self):
        """Канонический URL страницы"""
        if hasattr(self, 'object') and self.object:
            return self.request.build_absolute_uri(self.object.get_absolute_url())
        return self.request.build_absolute_uri()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Добавляем SEO-данные в контекст
        context['seo'] = {
            'title': self.get_seo_title(),
            'description': self.get_seo_description(),
            'keywords': self.get_seo_keywords(),
            'og_image': self.get_og_image(),
            'canonical_url': self.get_canonical_url(),
            'og_type': 'website',
            'twitter_card': 'summary_large_image',
        }
        
        return context


class ProductSEOMixin(SEOMixin):
    """
    Специализированный SEO-миксин для страниц товаров
    """
    
    def get_seo_title(self):
        if hasattr(self, 'object') and self.object:
            product = self.object
            # Используем meta_title из БД, если есть
            if product.meta_title:
                return product.meta_title
            brand_name = product.brand.name if product.brand else ''
            return f"{brand_name} {product.catalog_number} - {product.name} | TIR-Lugansk"
        return super().get_seo_title()
    
    def get_seo_description(self):
        if hasattr(self, 'object') and self.object:
            product = self.object
            # Используем meta_description из БД, если есть
            if product.meta_description:
                return product.meta_description
            desc = f"Купить {product.name}"
            if product.brand:
                desc += f" от {product.brand.name}"
            if product.catalog_number:
                desc += f" (арт. {product.catalog_number})"
            if product.price:
                desc += f". Цена: {product.price} руб."
            desc += " в интернет-магазине TIR-Lugansk. Доставка по Луганску."
            return desc
        return super().get_seo_description()
    
    def get_seo_keywords(self):
        if hasattr(self, 'object') and self.object:
            product = self.object
            # Используем meta_keywords из БД, если есть
            if product.meta_keywords:
                return product.meta_keywords
            keywords = [product.name]
            if product.brand:
                keywords.append(product.brand.name)
            if product.catalog_number:
                keywords.append(product.catalog_number)
            if product.category:
                keywords.append(product.category.name)
            keywords.extend(['автозапчасти', 'Луганск', 'купить'])
            return ', '.join(keywords)
        return super().get_seo_keywords()
    
    def get_og_image(self):
        if hasattr(self, 'object') and self.object:
            product = self.object
            # Пытаемся получить главное изображение товара
            main_image = product.images.filter(is_main=True).first()
            if main_image:
                return self.request.build_absolute_uri(main_image.url)
            # Или первое доступное
            first_image = product.images.first()
            if first_image:
                return self.request.build_absolute_uri(first_image.url)
        return super().get_og_image()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Добавляем structured data (Schema.org)
        if hasattr(self, 'object') and self.object:
            product = self.object
            context['seo']['structured_data'] = self.generate_product_schema(product)
            context['seo']['og_type'] = 'product'
        
        return context
    
    def generate_product_schema(self, product):
        """
        Генерация Schema.org разметки для товара
        """
        schema = {
            "@context": "https://schema.org/",
            "@type": "Product",
            "name": product.name,
            "sku": product.catalog_number or product.tmp_id,
        }
        
        if product.description:
            schema["description"] = product.description
        
        if product.brand:
            schema["brand"] = {
                "@type": "Brand",
                "name": product.brand.name
            }
        
        if product.images.exists():
            main_image = product.images.filter(is_main=True).first() or product.images.first()
            if main_image:
                schema["image"] = self.request.build_absolute_uri(main_image.url)
        
        if product.price and product.price > 0:
            schema["offers"] = {
                "@type": "Offer",
                "url": self.request.build_absolute_uri(product.get_absolute_url()),
                "priceCurrency": "RUB",
                "price": str(product.price),
                "availability": "https://schema.org/InStock" if product.in_stock else "https://schema.org/OutOfStock"
            }
        
        return schema


class CategorySEOMixin(SEOMixin):
    """
    Специализированный SEO-миксин для страниц категорий
    """
    
    def get_seo_title(self):
        if hasattr(self, 'category') and self.category:
            return f"{self.category.name} - Автозапчасти | TIR-Lugansk"
        return super().get_seo_title()
    
    def get_seo_description(self):
        if hasattr(self, 'category') and self.category:
            desc = f"Купить {self.category.name.lower()} в интернет-магазине TIR-Lugansk. "
            desc += f"Широкий выбор автозапчастей категории {self.category.name}. "
            desc += "Доставка по Луганску и области."
            return desc
        return super().get_seo_description()


def _sitemap_entry(loc, changefreq, priority, lastmod=None):
    return {
        "loc": loc,
        "changefreq": changefreq,
        "priority": priority,
        "lastmod": lastmod,
    }


def generate_sitemap_urls():
    """
    Список относительных URL для sitemap.xml (корень сайта, каталог, страницы, «Полезное», товары).
    """
    import logging

    from django.urls import reverse

    from pages.models import Page, UsefulCategory, UsefulPost
    from shop.models import Brand, Category, Product

    logger = logging.getLogger(__name__)
    urls = []

    urls.append(_sitemap_entry(reverse("pages:home"), "daily", "1.0"))
    catalog_path = reverse("shop:catalog")
    urls.append(_sitemap_entry(catalog_path, "daily", "0.9"))
    urls.append(_sitemap_entry(reverse("pages:about"), "monthly", "0.7"))
    urls.append(_sitemap_entry(reverse("pages:contacts"), "monthly", "0.7"))

    def _extend(section_name, builder):
        try:
            builder()
        except Exception as exc:
            logger.warning("Sitemap: пропущен блок «%s»: %s", section_name, exc)

    def _add_categories():
        for category in Category.objects.filter(is_active=True).only("slug"):
            urls.append(
                _sitemap_entry(
                    f"{catalog_path}?category={category.slug}",
                    "weekly",
                    "0.8",
                )
            )

    def _add_brands():
        for brand in Brand.objects.only("slug").iterator(chunk_size=500):
            urls.append(
                _sitemap_entry(f"{catalog_path}?brand={brand.slug}", "weekly", "0.7")
            )

    def _add_pages():
        for page in Page.objects.filter(is_active=True).only("slug", "updated_at"):
            urls.append(
                _sitemap_entry(
                    reverse("pages:page_detail", kwargs={"slug": page.slug}),
                    "monthly",
                    "0.5",
                    page.updated_at,
                )
            )

    def _add_useful_categories():
        for useful_category in UsefulCategory.objects.filter(is_active=True).only(
            "slug", "updated_at"
        ):
            urls.append(
                _sitemap_entry(
                    reverse("pages:useful_category", kwargs={"slug": useful_category.slug}),
                    "weekly",
                    "0.6",
                    useful_category.updated_at,
                )
            )

    def _add_useful_posts():
        for post in (
            UsefulPost.objects.filter(is_active=True)
            .only("id", "updated_at", "published_at")
            .iterator(chunk_size=500)
        ):
            lastmod = post.updated_at or post.published_at
            urls.append(
                _sitemap_entry(post.get_absolute_url(), "monthly", "0.5", lastmod)
            )

    def _add_products():
        for product in (
            Product.objects.filter(in_stock=True)
            .only("slug", "updated_at")
            .iterator(chunk_size=2000)
        ):
            urls.append(
                _sitemap_entry(
                    product.get_absolute_url(),
                    "weekly",
                    "0.6",
                    product.updated_at,
                )
            )

    _extend("categories", _add_categories)
    _extend("brands", _add_brands)
    _extend("pages", _add_pages)
    _extend("useful_categories", _add_useful_categories)
    _extend("useful_posts", _add_useful_posts)
    _extend("products", _add_products)

    return urls

