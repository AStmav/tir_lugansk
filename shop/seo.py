"""
SEO утилиты и миксины для оптимизации сайта под поисковые системы
"""
from urllib.parse import urlencode

from django.templatetags.static import static
from django.urls import reverse

SITE_NAME = "TIR-Lugansk"
DEFAULT_OG_IMAGE_PATH = "img/logo.png"
CANONICAL_EXCLUDE_PARAMS = frozenset({"page"})


def truncate_meta_text(text, length=160):
    text = " ".join((text or "").split())
    if len(text) <= length:
        return text
    truncated = text[:length].rsplit(" ", 1)[0]
    return f"{truncated}..."


def format_page_title(title, include_site=True):
    title = (title or "").strip()
    if not title:
        return SITE_NAME
    if not include_site or SITE_NAME in title:
        return title
    return f"{title} | {SITE_NAME}"


def default_og_image_url(request):
    return request.build_absolute_uri(static(DEFAULT_OG_IMAGE_PATH))


def build_canonical_url(request, path=None, query_dict=None, exclude_params=CANONICAL_EXCLUDE_PARAMS):
    path = path if path is not None else request.path
    query = query_dict if query_dict is not None else request.GET
    pairs = [
        (key, val)
        for key, values in query.lists()
        for val in values
        if key not in exclude_params
    ]
    if pairs:
        return request.build_absolute_uri(f"{path}?{urlencode(pairs, doseq=True)}")
    return request.build_absolute_uri(path)


def build_seo_context(
    request,
    *,
    title,
    description="",
    keywords="",
    canonical_url=None,
    og_type="website",
    og_image=None,
    twitter_card="summary_large_image",
    structured_data=None,
):
    if og_image is None:
        og_image = default_og_image_url(request)
    if canonical_url is None:
        canonical_url = build_canonical_url(request)
    elif isinstance(canonical_url, str) and canonical_url.startswith("/"):
        canonical_url = request.build_absolute_uri(canonical_url)

    return {
        "title": title,
        "description": description,
        "keywords": keywords,
        "og_image": og_image,
        "canonical_url": canonical_url,
        "og_type": og_type,
        "twitter_card": twitter_card,
        "structured_data": structured_data,
    }


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
        return getattr(self, 'og_image', default_og_image_url(self.request))
    
    def get_canonical_url(self):
        """Канонический URL страницы"""
        if hasattr(self, 'object') and self.object:
            return self.request.build_absolute_uri(self.object.get_absolute_url())
        return build_canonical_url(self.request)
    
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


class BrandSEOMixin(SEOMixin):
    """SEO-миксин для страниц бренда в каталоге."""

    def get_seo_title(self):
        if hasattr(self, 'brand') and self.brand:
            if self.brand.meta_title:
                return self.brand.meta_title
            return f"{self.brand.name} — автозапчасти | TIR-Lugansk"
        return super().get_seo_title()

    def get_seo_description(self):
        if hasattr(self, 'brand') and self.brand:
            if self.brand.meta_description:
                return self.brand.meta_description
            desc = f"Купить автозапчасти {self.brand.name} в интернет-магазине TIR-Lugansk. "
            desc += f"Оригинальные и аналоговые детали бренда {self.brand.name}. "
            desc += "Доставка по Луганску и области."
            return desc
        return super().get_seo_description()

    def get_seo_keywords(self):
        if hasattr(self, 'brand') and self.brand:
            if self.brand.meta_keywords:
                return self.brand.meta_keywords
            return f"{self.brand.name}, автозапчасти {self.brand.name}, купить {self.brand.name}, Луганск"
        return super().get_seo_keywords()

    def get_og_image(self):
        if hasattr(self, 'brand') and self.brand and self.brand.logo:
            return self.request.build_absolute_uri(self.brand.logo.url)
        return super().get_og_image()

    def get_canonical_url(self):
        if hasattr(self, 'brand') and self.brand:
            from shop.brand_urls import brand_canonical_url

            return self.request.build_absolute_uri(
                brand_canonical_url(self.brand.slug, self.request.GET)
            )
        return super().get_canonical_url()


class CategorySEOMixin(SEOMixin):
    """
    Специализированный SEO-миксин для страниц категорий
    """
    
    def get_seo_title(self):
        if hasattr(self, 'category') and self.category:
            if self.category.meta_title:
                return self.category.meta_title
            return f"{self.category.name} - Автозапчасти | {SITE_NAME}"
        return super().get_seo_title()
    
    def get_seo_description(self):
        if hasattr(self, 'category') and self.category:
            if self.category.meta_description:
                return self.category.meta_description
            desc = f"Купить {self.category.name.lower()} в интернет-магазине {SITE_NAME}. "
            desc += f"Широкий выбор автозапчастей категории {self.category.name}. "
            desc += "Доставка по Луганску и области."
            return desc
        return super().get_seo_description()

    def get_seo_keywords(self):
        if hasattr(self, 'category') and self.category and self.category.meta_keywords:
            return self.category.meta_keywords
        return super().get_seo_keywords()

    def get_canonical_url(self):
        if hasattr(self, 'category') and self.category:
            from shop.category_urls import category_canonical_url

            return self.request.build_absolute_uri(
                category_canonical_url(self.category.slug, self.request.GET)
            )
        return super().get_canonical_url()


def seo_brands_list(request, brands_count=0):
    title = format_page_title("Производители автозапчастей")
    description = (
        "Полный список брендов и производителей автозапчастей "
        "в интернет-магазине TIR-Lugansk. Выберите производителя и перейдите в каталог."
    )
    if brands_count:
        description = (
            f"Каталог из {brands_count} производителей автозапчастей. "
            "Выберите бренд и перейдите к товарам в наличии."
        )
    return build_seo_context(
        request,
        title=title,
        description=truncate_meta_text(description),
        keywords="производители автозапчастей, бренды запчастей, поставщики, TIR-Lugansk",
        canonical_url=reverse("shop:brands"),
    )


def _sitemap_entry(loc, changefreq, priority, lastmod=None):
    return {
        "loc": loc,
        "changefreq": changefreq,
        "priority": priority,
        "lastmod": lastmod,
    }


SITEMAP_SECTIONS = (
    ("products", "/sitemap-products.xml", "generate_sitemap_products_urls"),
    ("categories", "/sitemap-categories.xml", "generate_sitemap_categories_urls"),
    ("pages", "/sitemap-pages.xml", "generate_sitemap_pages_urls"),
)


def _sitemap_section_lastmod(entries):
    dates = [
        entry["lastmod"]
        for entry in entries
        if entry.get("lastmod") is not None and hasattr(entry["lastmod"], "strftime")
    ]
    return max(dates) if dates else None


def _run_sitemap_builder(section_name, builder, urls):
    import logging

    logger = logging.getLogger(__name__)
    try:
        builder(urls)
    except Exception as exc:
        logger.warning("Sitemap: пропущен блок «%s»: %s", section_name, exc)


def generate_sitemap_products_urls():
    """Карточки товаров в наличии."""
    from shop.models import Product

    urls = []

    def _add(urls_list):
        for product in (
            Product.objects.filter(in_stock=True)
            .only("slug", "updated_at")
            .iterator(chunk_size=2000)
        ):
            urls_list.append(
                _sitemap_entry(
                    product.get_absolute_url(),
                    "weekly",
                    "0.6",
                    product.updated_at,
                )
            )

    _run_sitemap_builder("products", _add, urls)
    return urls


def generate_sitemap_categories_urls():
    """Каталог, фильтры по категориям и брендам."""
    from django.urls import reverse

    from shop.models import Brand, Category

    urls = []
    catalog_path = reverse("shop:catalog")
    urls.append(_sitemap_entry(catalog_path, "daily", "0.9"))
    urls.append(_sitemap_entry(reverse("shop:brands"), "weekly", "0.8"))

    def _add_categories(urls_list):
        for category in Category.objects.filter(is_active=True).only("slug"):
            urls_list.append(
                _sitemap_entry(
                    reverse("shop:category", kwargs={"category_slug": category.slug}),
                    "weekly",
                    "0.8",
                )
            )

    def _add_brands(urls_list):
        for brand in Brand.objects.only("slug").iterator(chunk_size=500):
            urls_list.append(
                _sitemap_entry(
                    reverse("shop:brand", kwargs={"brand_slug": brand.slug}),
                    "weekly",
                    "0.7",
                )
            )

    _run_sitemap_builder("catalog_categories", _add_categories, urls)
    _run_sitemap_builder("brands", _add_brands, urls)
    return urls


def generate_sitemap_pages_urls():
    """Статические страницы, CMS, раздел «Полезное»."""
    from django.urls import reverse

    from pages.models import Page, UsefulCategory, UsefulPost

    urls = []
    urls.append(_sitemap_entry(reverse("pages:home"), "daily", "1.0"))
    urls.append(_sitemap_entry(reverse("pages:about"), "monthly", "0.7"))
    urls.append(_sitemap_entry(reverse("pages:contacts"), "monthly", "0.7"))

    def _add_pages(urls_list):
        for page in Page.objects.filter(is_active=True).only("slug", "updated_at"):
            urls_list.append(
                _sitemap_entry(
                    reverse("pages:page_detail", kwargs={"slug": page.slug}),
                    "monthly",
                    "0.5",
                    page.updated_at,
                )
            )

    def _add_useful_categories(urls_list):
        for useful_category in UsefulCategory.objects.filter(is_active=True).only(
            "slug", "updated_at"
        ):
            urls_list.append(
                _sitemap_entry(
                    useful_category.get_absolute_url(),
                    "weekly",
                    "0.6",
                    useful_category.updated_at,
                )
            )

    def _add_useful_posts(urls_list):
        for post in (
            UsefulPost.objects.filter(is_active=True)
            .only("id", "updated_at", "published_at")
            .iterator(chunk_size=500)
        ):
            lastmod = post.updated_at or post.published_at
            urls_list.append(
                _sitemap_entry(post.get_absolute_url(), "monthly", "0.5", lastmod)
            )

    _run_sitemap_builder("cms_pages", _add_pages, urls)
    _run_sitemap_builder("useful_categories", _add_useful_categories, urls)
    _run_sitemap_builder("useful_posts", _add_useful_posts, urls)
    return urls


def get_sitemap_section_urls(section_key):
    generators = {
        "products": generate_sitemap_products_urls,
        "categories": generate_sitemap_categories_urls,
        "pages": generate_sitemap_pages_urls,
    }
    generator = generators.get(section_key)
    if not generator:
        return None
    return generator()


def generate_sitemap_urls():
    """Все URL подряд (для совместимости и отладки)."""
    urls = []
    for _key, _path, generator_name in SITEMAP_SECTIONS:
        gen = globals()[generator_name]
        urls.extend(gen())
    return urls

