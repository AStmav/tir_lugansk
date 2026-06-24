"""Тесты Sitemap-классов (django.contrib.sitemaps)."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from pages.models import Page, UsefulCategory, UsefulPost
from shop.models import Brand, Category, Product
from shop.sitemaps import CategorySitemap, PageSitemap, ProductSitemap, SITEMAPS


class SitemapClassesTests(TestCase):
    def test_sitemaps_registry_keys(self):
        self.assertEqual(set(SITEMAPS.keys()), {"products", "categories", "pages"})

    def test_product_sitemap_only_in_stock(self):
        brand = Brand.objects.create(name="TestBrand", slug="test-brand")
        category = Category.objects.create(name="Cat", slug="cat")
        in_stock = Product.objects.create(
            name="In stock",
            slug="in-stock",
            code="T1",
            catalog_number="A1",
            price=Decimal("100.00"),
            brand=brand,
            category=category,
            in_stock=True,
        )
        Product.objects.create(
            name="Out of stock",
            slug="out-stock",
            code="T2",
            catalog_number="A2",
            price=Decimal("100.00"),
            brand=brand,
            category=category,
            in_stock=False,
        )

        sitemap = ProductSitemap()
        items = list(sitemap.items())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].pk, in_stock.pk)
        self.assertEqual(sitemap.location(items[0]), in_stock.get_absolute_url())

    def test_category_sitemap_static_and_entities(self):
        Category.objects.create(name="Cat", slug="cat", is_active=True)
        Brand.objects.create(name="Brand", slug="brand")

        sitemap = CategorySitemap()
        locations = [sitemap.location(item) for item in sitemap.items()]

        self.assertIn(reverse("shop:catalog"), locations)
        self.assertIn(reverse("shop:brands"), locations)
        self.assertIn(reverse("shop:category", kwargs={"category_slug": "cat"}), locations)
        self.assertIn(reverse("shop:brand", kwargs={"brand_slug": "brand"}), locations)

    def test_page_sitemap_static_and_cms(self):
        Page.objects.create(
            title="Custom",
            slug="custom-page",
            content="x",
            is_active=True,
        )
        useful_category = UsefulCategory.objects.create(
            title="Useful",
            slug="useful-cat",
            is_active=True,
        )
        post = UsefulPost.objects.create(
            category=useful_category,
            title="Post",
            content="body",
            is_active=True,
        )

        sitemap = PageSitemap()
        locations = [sitemap.location(item) for item in sitemap.items()]

        self.assertIn(reverse("pages:home"), locations)
        self.assertIn(reverse("pages:about"), locations)
        self.assertIn(reverse("pages:contacts"), locations)
        self.assertIn(
            reverse("pages:page_detail", kwargs={"slug": "custom-page"}),
            locations,
        )
        self.assertIn(useful_category.get_absolute_url(), locations)
        self.assertIn(post.get_absolute_url(), locations)

    def test_page_sitemap_lastmod_for_useful_post(self):
        useful_category = UsefulCategory.objects.create(
            title="Useful",
            slug="useful-cat",
            is_active=True,
        )
        post = UsefulPost.objects.create(
            category=useful_category,
            title="Post",
            content="body",
            is_active=True,
        )

        sitemap = PageSitemap()
        self.assertEqual(sitemap.lastmod(post), post.updated_at or post.published_at)


class SitemapPagesHttpTests(TestCase):
    def test_pages_sitemap_returns_xml(self):
        response = self.client.get("/sitemap-pages.xml")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml")
        self.assertIn(b"<urlset", response.content)
        self.assertIn(reverse("pages:home").encode(), response.content)


class SitemapCategoriesHttpTests(TestCase):
    def test_categories_sitemap_returns_xml(self):
        response = self.client.get("/sitemap-categories.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<urlset", response.content)
        self.assertIn(reverse("shop:catalog").encode(), response.content)


class SitemapProductsHttpTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Brand", slug="brand-prod")
        self.category = Category.objects.create(name="Cat", slug="cat-prod")
        self.product = Product.objects.create(
            name="Product",
            slug="product-prod",
            code="P1",
            catalog_number="111",
            price=Decimal("50.00"),
            brand=self.brand,
            category=self.category,
            in_stock=True,
        )

    def test_products_sitemap_returns_xml(self):
        response = self.client.get("/sitemap-products.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<urlset", response.content)
        self.assertIn(self.product.get_absolute_url().encode(), response.content)


class SitemapIndexHttpTests(TestCase):
    def test_index_lists_all_sections(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<sitemapindex", response.content)
        self.assertIn(b"sitemap-products.xml", response.content)
        self.assertIn(b"sitemap-categories.xml", response.content)
        self.assertIn(b"sitemap-pages.xml", response.content)
