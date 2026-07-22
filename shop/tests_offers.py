from decimal import Decimal

from django.test import TestCase

from shop.models import Brand, Category, Product, ProductOffer, Warehouse
from shop.offers import format_delivery_days, get_product_display_offers


class OffersHelpersTests(TestCase):
    def test_format_delivery_days(self):
        self.assertEqual(format_delivery_days(0), 'На складе')
        self.assertEqual(format_delivery_days(1), '1 день')
        self.assertEqual(format_delivery_days(3), '3 дня')
        self.assertEqual(format_delivery_days(5), '5 дн.')


class ProductDisplayOffersTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Тест', slug='test-cat-offers')
        self.brand = Brand.objects.create(name='TestBrand', slug='test-brand-offers')
        self.product = Product.objects.create(
            name='Тестовый товар',
            slug='test-product-offers',
            category=self.category,
            brand=self.brand,
            code='T1',
            catalog_number='ART-1',
            price=Decimal('1000.00'),
            in_stock=True,
            stock_quantity=4,
        )
        self.default_wh = Warehouse.objects.create(
            name_internal='Основной тест',
            name_public='LOCAL',
            delivery_days=0,
            is_active=True,
            is_default=True,
            sort_order=0,
        )

    def test_legacy_fallback_when_no_offers(self):
        rows = get_product_display_offers(self.product)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].is_legacy)
        self.assertEqual(rows[0].warehouse_public, 'LOCAL')
        self.assertEqual(rows[0].price, Decimal('1000.00'))
        self.assertEqual(rows[0].quantity_label, '4 шт.')
        self.assertEqual(rows[0].delivery_label, 'На складе')

    def test_multiple_warehouse_offers(self):
        wh2 = Warehouse.objects.create(
            name_internal='Мотор-Доктор1',
            name_public='VS_002',
            delivery_days=2,
            is_active=True,
            sort_order=10,
        )
        ProductOffer.objects.create(
            product=self.product,
            warehouse=self.default_wh,
            price=Decimal('1100.00'),
            stock_quantity=2,
        )
        ProductOffer.objects.create(
            product=self.product,
            warehouse=wh2,
            price=Decimal('980.00'),
            stock_quantity=5,
        )
        rows = get_product_display_offers(self.product)
        self.assertEqual(len(rows), 2)
        self.assertFalse(rows[0].is_legacy)
        publics = {r.warehouse_public for r in rows}
        self.assertEqual(publics, {'LOCAL', 'VS_002'})
        vs = next(r for r in rows if r.warehouse_public == 'VS_002')
        self.assertEqual(vs.delivery_label, '2 дня')
        self.assertEqual(vs.price, Decimal('980.00'))

    def test_warehouse_color_on_offer(self):
        self.default_wh.color = '#3CC14E'
        self.default_wh.save(update_fields=['color'])
        ProductOffer.objects.create(
            product=self.product,
            warehouse=self.default_wh,
            price=Decimal('1000.00'),
            stock_quantity=1,
        )
        rows = get_product_display_offers(self.product)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].warehouse_color, '#3CC14E')

    def test_inactive_warehouse_hidden(self):
        wh2 = Warehouse.objects.create(
            name_internal='Выкл',
            name_public='OFF',
            delivery_days=5,
            is_active=False,
            sort_order=20,
        )
        ProductOffer.objects.create(
            product=self.product,
            warehouse=self.default_wh,
            price=Decimal('1000.00'),
            stock_quantity=1,
        )
        ProductOffer.objects.create(
            product=self.product,
            warehouse=wh2,
            price=Decimal('500.00'),
            stock_quantity=99,
        )
        rows = get_product_display_offers(self.product)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].warehouse_public, 'LOCAL')
