"""Тесты команды regenerate_product_slugs (коллизии slug)."""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from shop.models import Brand, Category, Product, ProductSlugAlias
from shop.product_slugs import build_product_slug, uniquify_slug


class RegenerateProductSlugsCommandTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='ТестSlugCmd', slug='test-slug-cmd-cat')
        self.brand = Brand.objects.create(
            name='Autostandart',
            code='AUTOCMD',
            slug='autostandart-cmd',
        )

    def _create_product(self, suffix, name, catalog_number='108402'):
        return Product.objects.create(
            name=name,
            slug=f'legacy-vest-{suffix}',
            category=self.category,
            brand=self.brand,
            code=f'TMP-CMD-{suffix}',
            tmp_id=f'00020{suffix}',
            catalog_number=catalog_number,
            price=Decimal('100.00'),
        )

    def tearDown(self):
        ProductSlugAlias.objects.all().delete()
        Product.objects.filter(code__startswith='TMP-CMD-').delete()
        Brand.objects.filter(code='AUTOCMD').delete()
        Category.objects.filter(slug='test-slug-cmd-cat').delete()

    def test_duplicate_catalog_products_get_unique_slugs(self):
        """Два жилета 108402 Autostandart — разные финальные slug."""
        self._create_product('1', 'Жилет светоотражающий жёлтый размер M')
        self._create_product('2', 'Жилет светоотражающий жёлтый размер L')

        call_command('regenerate_product_slugs', '--apply')

        slugs = list(
            Product.objects.filter(code__startswith='TMP-CMD-')
            .order_by('code')
            .values_list('slug', flat=True)
        )
        self.assertEqual(len(slugs), 2)
        self.assertEqual(len(set(slugs)), 2)
        self.assertTrue(all(s.startswith('108402-autostandart-') for s in slugs))

    def test_vacate_and_claim_slug_in_same_batch(self):
        """Товар A освобождает slug, товар B забирает — без IntegrityError."""
        keeper = self._create_product(
            'k',
            'Жилет светоотражающий',
            catalog_number='108402',
        )
        target_slug = '108402-autostandart-zhilet-svetootrazhaiushchii-zh'
        keeper.slug = target_slug
        keeper.save(update_fields=['slug'])

        self._create_product(
            'o',
            'Жилет светоотражающий другой',
            catalog_number='108402',
        )

        call_command('regenerate_product_slugs', '--apply', '--batch-size', '10')

        slugs = list(
            Product.objects.filter(code__startswith='TMP-CMD-')
            .values_list('slug', flat=True)
        )
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_conflict_with_existing_unchanged_slug(self):
        """Товар уже занял целевой slug — второй не должен получить тот же."""
        owner = self._create_product('owner', 'Жилет светоотражающий', catalog_number='108402')
        owner.slug = '108402-autostandart-zhilet-svetootrazhaiushchii-zh'
        owner.save(update_fields=['slug'])

        other = self._create_product('other', 'Жилет светоотражающий жёлтый L')

        call_command('regenerate_product_slugs', '--apply')

        owner.refresh_from_db()
        other.refresh_from_db()
        self.assertNotEqual(other.slug, owner.slug)
        self.assertFalse(
            Product.objects.filter(slug=owner.slug).exclude(pk=owner.pk).exists()
        )

    def test_large_batch_with_duplicates(self):
        """Много товаров с одинаковым артикулом — без IntegrityError."""
        for i in range(20):
            self._create_product(
                f'b{i}',
                f'Жилет светоотражающий размер {i}',
                catalog_number='108402',
            )

        call_command('regenerate_product_slugs', '--apply', '--batch-size', '7')

        slugs = list(
            Product.objects.filter(code__startswith='TMP-CMD-')
            .values_list('slug', flat=True)
        )
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_planned_slugs_are_globally_unique(self):
        """Планирование не должно выдавать один new_slug двум товарам."""
        for i in range(5):
            self._create_product(str(i), f'Жилет светоотражающий вариант {i}')

        from shop.management.commands.regenerate_product_slugs import Command

        cmd = Command()
        reserved = cmd._load_reserved_slugs()
        planned_new = []

        for product in Product.objects.filter(
            code__startswith='TMP-CMD-'
        ).select_related('brand').order_by('id'):
            old_slug = product.slug
            brand_name = product.brand.name

            def is_taken(candidate, _old=old_slug):
                if candidate == _old:
                    return False
                return candidate in reserved

            new_slug = uniquify_slug(
                build_product_slug(product.catalog_number, brand_name, product.name),
                is_taken,
            )
            if new_slug == old_slug:
                continue
            reserved.add(new_slug)
            planned_new.append(new_slug)

        self.assertEqual(len(planned_new), len(set(planned_new)))
