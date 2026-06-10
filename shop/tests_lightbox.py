"""Тесты лайтбокса: URL галереи для карточек в списках."""
import json
from unittest.mock import PropertyMock, patch

from django.test import SimpleTestCase, TestCase

from shop.models import Brand, Category, Product, ProductImage
from shop.templatetags.product_tags import lightbox_images_json


class LightboxImagesJsonFilterTests(SimpleTestCase):
    def test_empty_returns_empty_string(self):
        self.assertEqual(lightbox_images_json([]), "")

    def test_json_contains_urls(self):
        result = lightbox_images_json(["/images/a.jpg", "/images/b.jpg"])
        self.assertIn("/images/a.jpg", result)
        self.assertIn("/images/b.jpg", result)


class ProductLightboxUrlsTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Тест", slug="test-lb")
        self.brand = Brand.objects.create(name="BrandLB", code="BLB", slug="brand-lb")
        self.product = Product.objects.create(
            name="Товар с галереей",
            slug="tovar-galereya",
            code="LB001",
            catalog_number="LB001",
            category=self.category,
            brand=self.brand,
            in_stock=True,
            price=100,
        )

    def test_single_image_no_extra_urls(self):
        ProductImage.objects.create(
            product=self.product,
            image="products/test1.jpg",
            order=0,
        )
        self.assertEqual(len(self.product.get_lightbox_image_urls()), 1)

    def test_multiple_images_unique_urls(self):
        ProductImage.objects.create(product=self.product, image="products/a.jpg", order=0)
        ProductImage.objects.create(product=self.product, image="products/b.jpg", order=1)
        urls = self.product.get_lightbox_image_urls()
        self.assertEqual(len(urls), 2)
        self.assertEqual(len(set(urls)), 2)

    @patch.object(Product, "has_main_image", new_callable=PropertyMock, return_value=True)
    @patch.object(Product, "main_image_url", new_callable=PropertyMock, return_value="/images/main.jpg")
    def test_main_image_plus_gallery(self, _mock_url, _mock_has):
        ProductImage.objects.create(product=self.product, image="products/extra.jpg", order=0)
        urls = self.product.get_lightbox_image_urls()
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], "/images/main.jpg")
