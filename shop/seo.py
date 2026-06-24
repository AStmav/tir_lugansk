"""
SEO утилиты и миксины для оптимизации сайта под поисковые системы
"""
import random
from urllib.parse import urlencode

from django.templatetags.static import static
from django.urls import reverse

SITE_NAME = "TIR-Lugansk"
DEFAULT_OG_IMAGE_PATH = "img/logo.png"
CANONICAL_EXCLUDE_PARAMS = frozenset({"page"})

DELIVERY_REGIONS = (
    'ЛНР',
    'Луганск',
    'Алчевск',
    'Стаханов',
    'Красный луч',
    'Северодонецк',
    'Марковка',
    'Беловодск',
    'Ростов',
    'Донецк',
    'ДНР',
    'Мариуполь',
    'Горловка',
)


def delivery_regions_sample(seed=0, count=5):
    """
    Стабильная «случайная» подборка регионов для meta.
    Один и тот же seed всегда даёт один набор — удобно для SEO и разнообразия по страницам.
    """
    count = min(max(count, 1), len(DELIVERY_REGIONS))
    regions = list(DELIVERY_REGIONS)
    rng = random.Random(seed)
    rng.shuffle(regions)
    return regions[:count]


def format_delivery_meta_phrase(seed=0, count=5):
    regions = delivery_regions_sample(seed, count)
    return f"Доставка: {', '.join(regions)}."


def delivery_region_keywords(seed=0, count=4):
    """Регионы для meta keywords (отдельный seed — другой набор, чем в description)."""
    return delivery_regions_sample(seed + 7919, count)


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
        return getattr(
            self,
            'seo_description',
            'Интернет-магазин автозапчастей в Луганске. '
            'Широкий ассортимент запчастей от проверенных производителей. '
            f'{format_delivery_meta_phrase(seed=0)}',
        )
    
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
            desc += (
                f" в интернет-магазине TIR-Lugansk. "
                f"{format_delivery_meta_phrase(seed=product.pk or 0)}"
            )
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
            keywords.extend(delivery_region_keywords(seed=product.pk or 0))
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
            desc += format_delivery_meta_phrase(seed=self.brand.pk or 0)
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
            desc += format_delivery_meta_phrase(seed=self.category.pk or 0)
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
        f"в интернет-магазине TIR-Lugansk. {format_delivery_meta_phrase(seed=42)}"
    )
    if brands_count:
        description = (
            f"Каталог из {brands_count} производителей автозапчастей. "
            f"Выберите бренд и перейдите к товарам в наличии. "
            f"{format_delivery_meta_phrase(seed=43)}"
        )
    return build_seo_context(
        request,
        title=title,
        description=truncate_meta_text(description),
        keywords="производители автозапчастей, бренды запчастей, поставщики, TIR-Lugansk",
        canonical_url=reverse("shop:brands"),
    )


