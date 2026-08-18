"""Тесты навигации к карточке товара (замечание заказчика)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from shop.admin_utils import product_nav_links, product_short_label
from shop.models import Brand, Category, Product, ProductOffer, Warehouse


class ProductNavLinksHelperTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Nav Cat', slug='nav-cat')
        self.brand = Brand.objects.create(name='NavBrand', slug='nav-brand', code='NVB')
        self.product = Product.objects.create(
            name='Навигационный фильтр',
            slug='nav-filter-product',
            category=self.category,
            brand=self.brand,
            code='NV001',
            catalog_number='CAT-777',
            price=Decimal('100'),
            in_stock=True,
        )

    def test_short_label_includes_brand_and_catalog(self):
        label = product_short_label(self.product)
        self.assertIn('NavBrand', label)
        self.assertIn('CAT-777', label)
        self.assertIn('Навигационный', label)

    def test_nav_links_contain_admin_and_site_urls(self):
        html = str(product_nav_links(self.product))
        self.assertIn(reverse('admin:shop_product_change', args=[self.product.pk]), html)
        self.assertIn(self.product.get_absolute_url(), html)
        self.assertIn('Админ', html)
        self.assertIn('Сайт', html)


class ProductAdminNavLinksTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username='nav_admin',
            email='nav@test.local',
            password='test-pass',
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.category = Category.objects.create(name='Admin Nav', slug='admin-nav-cat')
        self.brand = Brand.objects.create(name='AdminBrand', slug='admin-brand', code='ADB')
        self.product = Product.objects.create(
            name='Admin Nav Product',
            slug='admin-nav-product',
            category=self.category,
            brand=self.brand,
            code='ADB01',
            catalog_number='ADB-01',
            price=Decimal('50'),
            in_stock=True,
        )

    def test_product_changelist_shows_nav_links(self):
        url = reverse('admin:shop_product_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Админ')
        self.assertContains(response, self.product.get_absolute_url())
        self.assertContains(response, reverse('admin:shop_product_change', args=[self.product.pk]))


class ProductOfferAdminNavTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username='offer_nav_admin',
            email='offer@test.local',
            password='test-pass',
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.category = Category.objects.create(name='Offer Nav', slug='offer-nav-cat')
        self.brand = Brand.objects.create(name='OfferBrand', slug='offer-brand', code='OFR')
        self.product = Product.objects.create(
            name='Offer Nav Product',
            slug='offer-nav-product',
            category=self.category,
            brand=self.brand,
            code='OFR01',
            catalog_number='OFR-99',
            price=Decimal('10'),
            in_stock=True,
        )
        self.warehouse = Warehouse.objects.create(
            name_internal='Nav WH',
            name_public='NW',
            is_active=True,
        )
        ProductOffer.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            price=Decimal('12.50'),
            stock_quantity=3,
            is_active=True,
        )

    def test_offer_changelist_shows_product_nav_not_raw_id(self):
        url = reverse('admin:shop_productoffer_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OFR-99')
        self.assertContains(response, 'OfferBrand')
        self.assertContains(response, self.product.get_absolute_url())
        self.assertNotContains(response, f'{self.product.pk} @ {self.warehouse.pk}:')


class IndexNewProductsLinkTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='New Cat', slug='new-cat')
        self.brand = Brand.objects.create(name='NewBrand', slug='new-brand', code='NEW')
        self.product = Product.objects.create(
            name='New Product Link Test',
            slug='new-product-link-test',
            category=self.category,
            brand=self.brand,
            code='NEW01',
            catalog_number='NEW-01',
            price=Decimal('1'),
            in_stock=True,
            is_new=True,
        )

    def test_homepage_new_products_link_to_card(self):
        response = self.client.get(reverse('pages:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{self.product.get_absolute_url()}"',
            count=None,
        )


class JazzminRelatedModalSettingsTests(TestCase):
    def test_related_modal_disabled_for_full_page_edit(self):
        from django.conf import settings

        self.assertFalse(settings.JAZZMIN_SETTINGS.get('related_modal_active'))
