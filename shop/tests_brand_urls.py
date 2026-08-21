"""Тесты канонических URL брендов /shop/brand/<slug>/"""
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from shop.brand_urls import (
    brand_canonical_url,
    build_catalog_brand_redirect,
    resolve_active_brand_slug,
)
from shop.models import Brand, Category, Product


class BrandUrlHelperTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Bosch", code="BOSCH", slug="bosch-test")

    def test_resolve_slug(self):
        self.assertEqual(resolve_active_brand_slug("bosch-test"), "bosch-test")

    def test_resolve_legacy_short_slug(self):
        legacy = Brand.objects.create(
            name="Bosch Legacy",
            code="BOSCH2",
            slug="00000000552-bosch",
        )
        self.assertEqual(resolve_active_brand_slug("bosch"), legacy.slug)

    def test_resolve_by_name(self):
        Brand.objects.create(name="Mann-Filter", code="MANN", slug="mann-filter-x")
        self.assertEqual(resolve_active_brand_slug("Mann-Filter"), "mann-filter-x")

    def test_canonical_url(self):
        self.assertEqual(
            brand_canonical_url("bosch-test"),
            reverse("shop:brand", kwargs={"brand_slug": "bosch-test"}),
        )


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
)
class BrandPageViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.brand = Brand.objects.create(name="Bosch", code="BOSCH", slug="bosch-test")
        self.category = Category.objects.create(name="Фильтры", slug="filtry-brand-test")
        self.product = Product.objects.create(
            name="Товар Bosch",
            slug="tovar-bosch-test",
            code="B001",
            catalog_number="B001",
            category=self.category,
            brand=self.brand,
            in_stock=True,
            price=100,
        )

    def test_brand_page_returns_200(self):
        url = reverse("shop:brand", kwargs={"brand_slug": self.brand.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertContains(response, 'class="catalog__header"')
        self.assertContains(response, f'<h1>{self.brand.name}</h1>')

    def test_brand_page_shows_description(self):
        self.brand.description = "Немецкий производитель запчастей."
        self.brand.save(update_fields=["description"])
        url = reverse("shop:brand", kwargs={"brand_slug": self.brand.slug})
        response = self.client.get(url)
        self.assertContains(response, "Немецкий производитель запчастей.")

    def test_get_absolute_url_uses_brand_path(self):
        self.assertEqual(
            self.brand.get_absolute_url(),
            reverse("shop:brand", kwargs={"brand_slug": self.brand.slug}),
        )

    def test_brand_page_with_category_filter(self):
        url = reverse("shop:brand", kwargs={"brand_slug": self.brand.slug})
        response = self.client.get(url, {"category": self.category.slug})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)


@override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
)
class CatalogBrandRedirectTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.request_factory = RequestFactory()
        self.brand = Brand.objects.create(name="Mann", code="MANN", slug="mann-test")
        self.category = Category.objects.create(name="Масла", slug="masla-brand-test")

    def test_short_slug_redirects_to_canonical(self):
        Brand.objects.create(name="Bosch", code="BOSCH2", slug="00000000552-bosch")
        response = self.client.get(
            reverse("shop:brand", kwargs={"brand_slug": "bosch"}),
        )
        self.assertEqual(response.status_code, 301)
        self.assertIn("00000000552-bosch", response["Location"])

    def test_single_brand_query_redirects_301(self):
        catalog_url = reverse("shop:catalog")
        response = self.client.get(catalog_url, {"brand": self.brand.slug})
        self.assertEqual(response.status_code, 301)
        expected = reverse("shop:brand", kwargs={"brand_slug": self.brand.slug})
        self.assertEqual(response["Location"], expected)

    def test_redirect_preserves_sort_param(self):
        catalog_url = reverse("shop:catalog")
        response = self.client.get(catalog_url, {"brand": self.brand.slug, "sort": "name"})
        self.assertEqual(response.status_code, 301)
        self.assertIn("/shop/brand/mann-test/", response["Location"])
        self.assertIn("sort=name", response["Location"])
        self.assertNotIn("brand=", response["Location"])

    def test_no_redirect_with_search(self):
        request = self.request_factory.get(
            "/shop/catalog/",
            {"brand": self.brand.slug, "search": "test"},
        )
        self.assertIsNone(build_catalog_brand_redirect(request))

    def test_no_redirect_with_category(self):
        request = self.request_factory.get(
            "/shop/catalog/",
            {"brand": self.brand.slug, "category": self.category.slug},
        )
        self.assertIsNone(build_catalog_brand_redirect(request))

    def test_no_redirect_multiple_brands(self):
        other = Brand.objects.create(name="Other", code="OTH", slug="other-brand-test")
        request = self.request_factory.get(
            "/shop/catalog/",
            {"brand": [self.brand.slug, other.slug]},
        )
        self.assertIsNone(build_catalog_brand_redirect(request))

    def test_category_redirect_takes_priority_over_brand(self):
        catalog_url = reverse("shop:catalog")
        response = self.client.get(
            catalog_url,
            {"category": self.category.slug, "brand": self.brand.slug},
        )
        self.assertEqual(response.status_code, 301)
        self.assertIn("/shop/category/masla-brand-test/", response["Location"])
        self.assertIn("brand=mann-test", response["Location"])
