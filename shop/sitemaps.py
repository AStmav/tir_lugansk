"""
Sitemap-классы на базе django.contrib.sitemaps.
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

_STATIC_PAGES = ("home", "about", "contacts")
_STATIC_CATALOG = ("catalog", "brands")


class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    date_field = "updated_at"
    limit = 50000

    def items(self):
        from shop.models import Product

        return Product.objects.filter(in_stock=True).only("slug", "updated_at")

    def location(self, obj):
        return obj.get_absolute_url()


class CategorySitemap(Sitemap):
    def items(self):
        from shop.models import Brand, Category

        items = list(_STATIC_CATALOG)
        items.extend(Category.objects.filter(is_active=True).only("slug"))
        items.extend(Brand.objects.only("slug"))
        return items

    def location(self, obj):
        if obj == "catalog":
            return reverse("shop:catalog")
        if obj == "brands":
            return reverse("shop:brands")
        if hasattr(obj, "parent"):
            return obj.get_absolute_url()
        return reverse("shop:brand", kwargs={"brand_slug": obj.slug})

    def changefreq(self, obj):
        if obj == "catalog":
            return "daily"
        return "weekly"

    def priority(self, obj):
        if obj == "catalog":
            return 0.9
        if obj == "brands" or hasattr(obj, "parent"):
            return 0.8
        return 0.7


class PageSitemap(Sitemap):
    def items(self):
        from pages.models import Page, UsefulCategory, UsefulPost

        items = list(_STATIC_PAGES)
        items.extend(Page.objects.filter(is_active=True).only("slug", "updated_at"))
        items.extend(
            UsefulCategory.objects.filter(is_active=True).only("slug", "updated_at")
        )
        items.extend(
            UsefulPost.objects.filter(is_active=True).only(
                "id", "updated_at", "published_at"
            )
        )
        return items

    def location(self, obj):
        if obj in _STATIC_PAGES:
            return reverse(f"pages:{obj}")
        return obj.get_absolute_url()

    def changefreq(self, obj):
        if obj == "home":
            return "daily"
        if obj in _STATIC_PAGES:
            return "monthly"
        from pages.models import UsefulCategory

        if isinstance(obj, UsefulCategory):
            return "weekly"
        return "monthly"

    def priority(self, obj):
        if obj == "home":
            return 1.0
        if obj in _STATIC_PAGES:
            return 0.7
        from pages.models import Page, UsefulCategory

        if isinstance(obj, Page):
            return 0.5
        if isinstance(obj, UsefulCategory):
            return 0.6
        return 0.5

    def lastmod(self, obj):
        from pages.models import UsefulPost

        if obj in _STATIC_PAGES:
            return None
        if isinstance(obj, UsefulPost):
            return obj.updated_at or obj.published_at
        return getattr(obj, "updated_at", None)


SITEMAPS = {
    "products": ProductSitemap,
    "categories": CategorySitemap,
    "pages": PageSitemap,
}
