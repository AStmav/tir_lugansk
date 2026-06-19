"""Тесты SEO-утилит без БД."""
from django.test import RequestFactory, SimpleTestCase

from shop.seo import (
    build_canonical_url,
    delivery_regions_sample,
    format_delivery_meta_phrase,
    format_page_title,
    truncate_meta_text,
)


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

    def test_delivery_regions_sample_stable_for_same_seed(self):
        first = delivery_regions_sample(seed=123, count=5)
        second = delivery_regions_sample(seed=123, count=5)
        self.assertEqual(first, second)

    def test_delivery_regions_sample_differs_by_seed(self):
        a = delivery_regions_sample(seed=1, count=5)
        b = delivery_regions_sample(seed=2, count=5)
        self.assertNotEqual(a, b)

    def test_delivery_regions_sample_only_valid_regions(self):
        sample = delivery_regions_sample(seed=99, count=5)
        self.assertEqual(len(sample), 5)
        for region in sample:
            self.assertIn(region, (
                'ЛНР', 'Луганск', 'Алчевск', 'Стаханов', 'Красный луч',
                'Северодонецк', 'Марковка', 'Беловодск', 'Ростов',
                'Донецк', 'ДНР', 'Мариуполь', 'Горловка',
            ))

    def test_format_delivery_meta_phrase(self):
        phrase = format_delivery_meta_phrase(seed=7, count=3)
        self.assertTrue(phrase.startswith('Доставка: '))
        self.assertTrue(phrase.endswith('.'))
        self.assertEqual(phrase.count(','), 2)
