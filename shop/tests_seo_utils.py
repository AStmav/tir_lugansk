"""Тесты SEO-утилит без БД."""
from django.test import RequestFactory, SimpleTestCase

from shop.seo import build_canonical_url, format_page_title, truncate_meta_text


class SeoUtilsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_format_page_title_adds_site_name(self):
        self.assertEqual(format_page_title("Контакты"), "Контакты | TIR-Lugansk")

    def test_format_page_title_skips_duplicate_site_name(self):
        self.assertEqual(
            format_page_title("TIR-Lugansk - Главная"),
            "TIR-Lugansk - Главная",
        )

    def test_truncate_meta_text(self):
        text = "a " * 100
        self.assertLessEqual(len(truncate_meta_text(text, 50)), 53)

    def test_build_canonical_url_strips_page_param(self):
        request = self.factory.get("/shop/catalog/", {"page": "2", "sort": "name"})
        canonical = build_canonical_url(request)
        self.assertNotIn("page=", canonical)
        self.assertIn("sort=name", canonical)

    def test_build_canonical_url_path_only_without_query(self):
        request = self.factory.get("/shop/catalog/", {"page": "2"})
        canonical = build_canonical_url(request)
        self.assertTrue(canonical.endswith("/shop/catalog/"))
