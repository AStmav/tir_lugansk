import csv
import tempfile
from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from shop.models import Brand, Category, OeKod, Product, ProductOffer, Warehouse
from shop.warehouse_price.columns import resolve_column_index
from shop.warehouse_price.matcher import ProductMatcher
from shop.warehouse_price.normalize import parse_price, parse_quantity
from shop.warehouse_price.parser import iter_price_rows
from shop.warehouse_price.prefixes import article_variants
from shop.warehouse_price.service import run_warehouse_price_import


class WarehousePriceNormalizeTests(TestCase):
    def test_parse_price_comma(self):
        self.assertEqual(parse_price('1525,60'), Decimal('1525.60'))

    def test_parse_quantity(self):
        self.assertEqual(parse_quantity('20'), 20)
        self.assertEqual(parse_quantity('+'), 0)

    def test_parse_quantity_decimal_formats_not_thousands(self):
        """Замечание заказчика: 4.000 / 4,000 → 4 шт., не 4000."""
        self.assertEqual(parse_quantity('4.000'), 4)
        self.assertEqual(parse_quantity('4,000'), 4)
        self.assertEqual(parse_quantity('4.0'), 4)
        self.assertEqual(parse_quantity(4.0), 4)
        self.assertEqual(parse_quantity(4), 4)
        self.assertEqual(parse_quantity(Decimal('4.000')), 4)


class WarehousePriceColumnsTests(TestCase):
    def test_resolve_by_header(self):
        headers = ['Код', 'Бренд', 'Цена', 'Остаток']
        self.assertEqual(resolve_column_index('Бренд', headers), 1)
        self.assertEqual(resolve_column_index('B', headers), 1)


class WarehousePriceImportIntegrationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Cat', slug='cat-wh-price')
        self.brand = Brand.objects.create(name='TestBrandWH', slug='test-brand-wh', code='TBWH')
        self.product = Product.objects.create(
            name='WH Price Product',
            slug='wh-price-product',
            category=self.category,
            brand=self.brand,
            code='WH001',
            tmp_id='WH001',
            catalog_number='ART-900',
            price=Decimal('0'),
            in_stock=True,
        )
        self.product.catalog_number_clean = Product.clean_number('ART-900')
        self.product.save()
        self.warehouse = Warehouse.objects.create(
            name_internal='Import WH',
            name_public='IMP',
            delivery_days=1,
            is_active=True,
            sort_order=5,
        )

    def _write_csv(self, rows):
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8')
        writer = csv.writer(tmp, delimiter=';')
        for row in rows:
            writer.writerow(row)
        tmp.close()
        return tmp.name

    def test_import_by_brand_and_article(self):
        path = self._write_csv([
            ['Код', 'Бренд', 'Цена', 'Остаток'],
            ['ART-900', 'TBWH', '1250,50', '7'],
        ])
        try:
            settings = {
                'header_row': 1,
                'data_start_row': 2,
                'columns': {
                    'article': 'Код',
                    'brand': 'Бренд',
                    'price': 'Цена',
                    'qty': 'Остаток',
                },
            }
            stats = run_warehouse_price_import(
                warehouse=self.warehouse,
                file_path=path,
                import_settings=settings,
            )
            self.assertEqual(stats.total, 1)
            self.assertEqual(stats.updated, 1)
            offer = ProductOffer.objects.get(product=self.product, warehouse=self.warehouse)
            self.assertEqual(offer.price, Decimal('1250.50'))
            self.assertEqual(offer.stock_quantity, 7)
            self.product.refresh_from_db()
            self.assertEqual(self.product.price, Decimal('1250.50'))
            self.assertEqual(self.product.stock_quantity, 7)
            self.assertTrue(self.product.in_stock)
            self.warehouse.refresh_from_db()
            self.assertIsNotNone(self.warehouse.last_uploaded_at)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_import_syncs_catalog_price_and_parses_qty_like_customer_case(self):
        """
        Сценарий заказчика: цена есть на карточке (оффер), должна появиться в каталоге;
        остаток «4.000» → 4 шт.
        """
        path = self._write_csv([
            ['Код', 'Бренд', 'Цена', 'Остаток'],
            ['ART-900', 'TBWH', '1144', '4.000'],
        ])
        try:
            settings = {
                'header_row': 1,
                'data_start_row': 2,
                'columns': {
                    'article': 'Код',
                    'brand': 'Бренд',
                    'price': 'Цена',
                    'qty': 'Остаток',
                },
            }
            stats = run_warehouse_price_import(
                warehouse=self.warehouse,
                file_path=path,
                import_settings=settings,
            )
            self.assertEqual(stats.updated, 1)
            offer = ProductOffer.objects.get(product=self.product, warehouse=self.warehouse)
            self.assertEqual(offer.price, Decimal('1144.00'))
            self.assertEqual(offer.stock_quantity, 4)
            self.product.refresh_from_db()
            self.assertEqual(self.product.price, Decimal('1144.00'))
            self.assertEqual(self.product.stock_quantity, 4)
            self.assertTrue(self.product.in_stock)
            # Как в шаблоне каталога: {% if product.price %}
            self.assertTrue(bool(self.product.price))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_import_by_tmp_id(self):
        path = self._write_csv([
            ['Код ID', 'Цена', 'Остаток'],
            ['WH001', '999', '3'],
        ])
        try:
            settings = {
                'header_row': 1,
                'data_start_row': 2,
                'columns': {
                    'article': 'A',
                    'price': 'B',
                    'qty': 'C',
                    'external_id': 'Код ID',
                },
                'fixed_brand_id': self.brand.pk,
            }
            stats = run_warehouse_price_import(
                warehouse=self.warehouse,
                file_path=path,
                import_settings=settings,
            )
            self.assertEqual(stats.updated, 1)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_parser_skips_empty_article(self):
        path = self._write_csv([
            ['Код', 'Цена'],
            ['', '100'],
            ['ART-900', '200'],
        ])
        try:
            rows = list(
                iter_price_rows(
                    path,
                    header_row=1,
                    data_start_row=2,
                    column_map={'article': 'Код', 'price': 'Цена'},
                )
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].article, 'ART-900')
        finally:
            Path(path).unlink(missing_ok=True)

    def test_matcher_ambiguous_tmp_id(self):
        Product.objects.create(
            name='Dup',
            slug='wh-dup',
            category=self.category,
            brand=self.brand,
            code='WH001',
            tmp_id='WH001',
            catalog_number='DUP-1',
            price=Decimal('0'),
            in_stock=True,
        )
        matcher = ProductMatcher()
        product, reason = matcher.find_by_external_id('WH001')
        self.assertIsNone(product)
        self.assertIn('неоднознач', reason)


class WarehouseMarkupTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(
            name_internal='Markup WH',
            name_public='MK',
            is_active=True,
        )

    def test_percent_markup(self):
        self.warehouse.markup_mode = Warehouse.MARKUP_PERCENT
        self.warehouse.markup_percent = Decimal('23')
        self.warehouse.save()
        from shop.warehouse_price.markup import apply_markup
        self.assertEqual(apply_markup(self.warehouse, Decimal('1000')), Decimal('1230.00'))

    def test_range_markup(self):
        from shop.models import WarehouseMarkupRange
        from shop.warehouse_price.markup import apply_markup

        self.warehouse.markup_mode = Warehouse.MARKUP_RANGES
        self.warehouse.save()
        WarehouseMarkupRange.objects.create(
            warehouse=self.warehouse,
            price_from=Decimal('0'),
            price_to=Decimal('1000'),
            percent=Decimal('30'),
        )
        WarehouseMarkupRange.objects.create(
            warehouse=self.warehouse,
            price_from=Decimal('1001'),
            price_to=Decimal('10000'),
            percent=Decimal('25'),
        )
        WarehouseMarkupRange.objects.create(
            warehouse=self.warehouse,
            price_from=Decimal('10001'),
            price_to=Decimal('100000'),
            percent=Decimal('15'),
        )
        self.assertEqual(apply_markup(self.warehouse, Decimal('500')), Decimal('650.00'))
        self.assertEqual(apply_markup(self.warehouse, Decimal('5000')), Decimal('6250.00'))
        self.assertEqual(apply_markup(self.warehouse, Decimal('20000')), Decimal('23000.00'))

    def test_import_applies_percent_markup(self):
        category = Category.objects.create(name='CatM', slug='cat-markup')
        brand = Brand.objects.create(name='BrandM', slug='brand-m', code='BM')
        product = Product.objects.create(
            name='Markup Product',
            slug='markup-product',
            category=category,
            brand=brand,
            code='MK1',
            tmp_id='MK1',
            catalog_number='MK-ART',
            price=Decimal('0'),
            in_stock=True,
        )
        product.catalog_number_clean = Product.clean_number('MK-ART')
        product.save()

        self.warehouse.markup_mode = Warehouse.MARKUP_PERCENT
        self.warehouse.markup_percent = Decimal('23')
        self.warehouse.save()

        path = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8')
        writer = csv.writer(path, delimiter=';')
        writer.writerow(['Код', 'Бренд', 'Цена', 'Остаток'])
        writer.writerow(['MK-ART', 'BM', '1000', '2'])
        path.close()
        try:
            stats = run_warehouse_price_import(
                warehouse=self.warehouse,
                file_path=path.name,
                import_settings={
                    'header_row': 1,
                    'data_start_row': 2,
                    'columns': {
                        'article': 'Код',
                        'brand': 'Бренд',
                        'price': 'Цена',
                        'qty': 'Остаток',
                    },
                },
            )
            self.assertEqual(stats.updated, 1)
            offer = ProductOffer.objects.get(product=product, warehouse=self.warehouse)
            self.assertEqual(offer.price, Decimal('1230.00'))
        finally:
            Path(path.name).unlink(missing_ok=True)


class ArticlePrefixAndOeMatcherTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Cat2', slug='cat-prefix-oe')
        self.brand = Brand.objects.create(name='SE-M', slug='se-m-test', code='SEMTEST')
        self.product = Product.objects.create(
            name='SEM Part',
            slug='sem-part-test',
            category=self.category,
            brand=self.brand,
            code='SEM1',
            tmp_id='SEM1',
            catalog_number='7838',
            price=Decimal('0'),
            in_stock=True,
        )
        self.product.catalog_number_clean = Product.clean_number('7838')
        self.product.save()

    def test_article_variants_strip_and_add_prefix(self):
        variants = article_variants(self.brand, 'SEM7838')
        self.assertIn('sem7838', variants)
        self.assertIn('7838', variants)

        variants2 = article_variants(self.brand, '7838')
        self.assertIn('7838', variants2)
        self.assertIn('sem7838', variants2)

    def test_match_with_prefix_to_bare_catalog(self):
        matcher = ProductMatcher()
        product, reason = matcher.match(article='SEM7838', brand_text='SE-M')
        self.assertEqual(product, self.product)
        self.assertEqual(reason, '')

    def test_match_via_oe(self):
        auger = Brand.objects.create(name='Auger', slug='auger-test', code='AUGTEST')
        oe_owner = Product.objects.create(
            name='OE Owner',
            slug='oe-owner',
            category=self.category,
            brand=Brand.objects.create(name='OtherBrand', slug='other-brand-oe', code='OB1'),
            code='OE1',
            tmp_id='OE1',
            catalog_number='X-1',
            price=Decimal('0'),
            in_stock=True,
        )
        OeKod.objects.create(
            id_oe='OE-TEST-1',
            product=oe_owner,
            brand=auger,
            oe_kod='51566',
            oe_kod_clean=Product.clean_number('51566'),
            id_tovar='OE1',
        )

        matcher = ProductMatcher()
        # Auger + AUG51566 → варианты aug51566 / 51566 → OE 51566 у Auger
        product, reason = matcher.match(article='AUG51566', brand_text='Auger')
        self.assertEqual(product, oe_owner)
        self.assertEqual(reason, '')


class BrandAliasMatcherTests(TestCase):
    def setUp(self):
        from shop.models import BrandAlias

        self.category = Category.objects.create(name='CatAlias', slug='cat-alias')
        self.cummins = Brand.objects.create(name='Cummins', slug='cummins-alias', code='CUM')
        self.product = Product.objects.create(
            name='Cummins Filter',
            slug='cummins-filter-alias',
            category=self.category,
            brand=self.cummins,
            code='CUM1',
            tmp_id='CUM1',
            catalog_number='3927063',
            price=Decimal('0'),
            in_stock=True,
        )
        self.product.catalog_number_clean = Product.clean_number('3927063')
        self.product.save()
        BrandAlias.objects.create(brand=self.cummins, alias='Cummins Ch')

        self.mercedes = Brand.objects.create(
            name='Mercedes Benz', slug='mercedes-benz-alias', code='MB'
        )
        self.mb_product = Product.objects.create(
            name='MB Part',
            slug='mb-part-alias',
            category=self.category,
            brand=self.mercedes,
            code='MB1',
            tmp_id='MB1',
            catalog_number='A0000903751',
            price=Decimal('0'),
            in_stock=True,
        )
        self.mb_product.catalog_number_clean = Product.clean_number('A0000903751')
        self.mb_product.save()

        self.depo = Brand.objects.create(name='DEPO', slug='depo-alias', code='DEPO')
        self.marshall = Brand.objects.create(name='Marshall', slug='marshall-alias', code='MAR')
        self.glass = Product.objects.create(
            name='Mirror glass',
            slug='mirror-glass-alias',
            category=self.category,
            brand=self.depo,
            code='000152990',
            tmp_id='000152990',
            catalog_number='PED04AC0G00N',
            price=Decimal('0'),
            in_stock=True,
        )
        OeKod.objects.create(
            id_oe='OE-MAR-M4300070',
            product=self.glass,
            brand=self.marshall,
            oe_kod='M4300070',
            oe_kod_clean=Product.clean_number('M4300070'),
            id_tovar='000152990',
        )

    def test_alias_resolves_cummins_ch(self):
        matcher = ProductMatcher()
        product, reason = matcher.match(article='3927063', brand_text='Cummins Ch')
        self.assertEqual(product, self.product)
        self.assertEqual(reason, '')

    def test_normalize_mercedes_benz_hyphen(self):
        matcher = ProductMatcher()
        product, reason = matcher.match(article='A0000903751', brand_text='MERCEDES-BENZ')
        self.assertEqual(product, self.mb_product)
        self.assertEqual(reason, '')

    def test_match_via_oe_marshall_to_depo_card(self):
        """Прайс Marshall M4300070 → карточка DEPO через Аналоги OE."""
        matcher = ProductMatcher()
        product, reason = matcher.match(article='M4300070', brand_text='Marshall')
        self.assertEqual(product, self.glass)
        self.assertEqual(product.tmp_id, '000152990')
        self.assertEqual(reason, '')


class ImportPresetsTests(TestCase):
    def test_kt_center_preset_builds_settings(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from shop.forms.warehouse_price_form import WarehousePriceUploadForm
        from shop.warehouse_price.presets import get_preset_settings, match_preset_key

        upload = SimpleUploadedFile('t.csv', b'a;b\n1;2', content_type='text/csv')
        form = WarehousePriceUploadForm(
            data={
                'preset': 'kt_center',
                'header_row': 99,
                'data_start_row': 99,
                'col_article': '',
                'col_price': '',
                'save_mapping': True,
            },
            files={'file': upload},
        )
        self.assertTrue(form.is_valid(), form.errors)
        settings = form.build_import_settings()
        expected = get_preset_settings('kt_center')
        self.assertEqual(settings['header_row'], expected['header_row'])
        self.assertEqual(settings['columns']['article'], 'Обозначение')
        self.assertEqual(settings['preset'], 'kt_center')
        self.assertEqual(match_preset_key(settings), 'kt_center')

    def test_custom_requires_article_and_price(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from shop.forms.warehouse_price_form import WarehousePriceUploadForm

        upload = SimpleUploadedFile('t.csv', b'a;b\n1;2', content_type='text/csv')
        form = WarehousePriceUploadForm(
            data={
                'preset': 'custom',
                'header_row': 1,
                'data_start_row': 2,
                'col_article': '',
                'col_price': '',
            },
            files={'file': upload},
        )
        self.assertFalse(form.is_valid())
        self.assertIn('col_article', form.errors)
        self.assertIn('col_price', form.errors)

    def test_match_preset_from_saved_columns(self):
        from shop.warehouse_price.presets import match_preset_key

        self.assertEqual(
            match_preset_key({
                'header_row': 5,
                'data_start_row': 6,
                'columns': {
                    'article': 'Код',
                    'brand': 'Бренд',
                    'price': 'Цена',
                    'qty': 'Остаток',
                    'external_id': 'Код ID',
                },
            }),
            'price_a',
        )
