"""Тесты генерации slug товаров (без БД)."""
from django.test import SimpleTestCase

from shop.product_slugs import (
    build_product_slug,
    make_product_slug,
    slug_part,
    uniquify_slug,
)


class ProductSlugBuildTests(SimpleTestCase):
    def test_slug_part_translit_cyrillic(self):
        self.assertEqual(slug_part('Щетка дворника'), 'shchetka-dvornika')

    def test_build_product_slug_full(self):
        slug = build_product_slug(
            'NS03-G2',
            'Auger',
            'Штуцер топл. трубки 90* (трубка 12)',
        )
        self.assertEqual(
            slug,
            'ns03-g2-auger-shtutser-topl-trubki-90-trubka-12',
        )

    def test_build_product_slug_skips_duplicate_parts(self):
        slug = build_product_slug('GY004020', 'Good Year', 'Зимняя щетка')
        self.assertEqual(slug, 'gy004020-good-year-zimniaia-shchetka')

    def test_uniquify_slug_adds_suffix(self):
        taken = {'ns03-g2-auger-test'}
        slug = uniquify_slug('ns03-g2-auger-test', lambda s: s in taken)
        self.assertEqual(slug, 'ns03-g2-auger-test-2')

    def test_make_product_slug_respects_is_taken(self):
        slug = make_product_slug(
            '12.12108',
            'Kahveci',
            'Крыло',
            is_taken=lambda s: s == '1212108-kahveci-krylo',
        )
        self.assertEqual(slug, '1212108-kahveci-krylo-2')
