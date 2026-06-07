"""Тесты канонических URL категорий /shop/category/<slug>/"""
from django.http import QueryDict
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from shop.category_urls import (
    build_catalog_category_redirect,
    category_canonical_url,
    resolve_active_category_slug,
)
from shop.models import Brand, Category, Product


class CategoryUrlHelperTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Двигатель', slug='dvigatel-test')

    def test_resolve_slug(self):
        self.assertEqual(resolve_active_category_slug('dvigatel-test'), 'dvigatel-test')

    def test_resolve_numeric_id(self):
        self.assertEqual(resolve_active_category_slug(str(self.category.id)), 'dvigatel-test')

    def test_canonical_url(self):
        self.assertEqual(
            category_canonical_url('dvigatel-test'),
            reverse('shop:category', kwargs={'category_slug': 'dvigatel-test'}),
        )

    def test_canonical_url_excludes_page_param(self):
        query = QueryDict('sort=name&page=3')
        url = category_canonical_url('dvigatel-test', query)
        self.assertNotIn('page=', url)
        self.assertIn('sort=name', url)


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class CategoryPageViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name='Фильтры', slug='filtry-test')
        self.brand = Brand.objects.create(name='TestBrand', code='TBCT', slug='tbct')
        self.product = Product.objects.create(
            name='Товар в категории',
            slug='tovar-v-kategorii',
            code='CAT001',
            catalog_number='CAT001',
            category=self.category,
            brand=self.brand,
            in_stock=True,
            price=100,
        )

    def test_category_page_returns_200(self):
        url = reverse('shop:category', kwargs={'category_slug': self.category.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)

    def test_inactive_category_returns_404(self):
        self.category.is_active = False
        self.category.save(update_fields=['is_active'])
        url = reverse('shop:category', kwargs={'category_slug': self.category.slug})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_get_absolute_url_uses_category_path(self):
        self.assertEqual(
            self.category.get_absolute_url(),
            reverse('shop:category', kwargs={'category_slug': self.category.slug}),
        )


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class CatalogCategoryRedirectTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.request_factory = RequestFactory()
        self.category = Category.objects.create(name='Тормоза', slug='tormoza-test')

    def test_single_category_query_redirects_301(self):
        catalog_url = reverse('shop:catalog')
        response = self.client.get(catalog_url, {'category': self.category.slug})
        self.assertEqual(response.status_code, 301)
        expected = reverse('shop:category', kwargs={'category_slug': self.category.slug})
        self.assertEqual(response['Location'], expected)

    def test_redirect_preserves_other_params(self):
        catalog_url = reverse('shop:catalog')
        response = self.client.get(
            catalog_url,
            {'category': str(self.category.id), 'brand': 'x', 'sort': 'name'},
        )
        self.assertEqual(response.status_code, 301)
        self.assertIn('/shop/category/tormoza-test/', response['Location'])
        self.assertIn('brand=x', response['Location'])
        self.assertIn('sort=name', response['Location'])
        self.assertNotIn('category=', response['Location'])

    def test_no_redirect_with_search(self):
        request = self.request_factory.get(
            '/shop/catalog/',
            {'category': self.category.slug, 'search': 'test'},
        )
        self.assertIsNone(build_catalog_category_redirect(request))

    def test_no_redirect_multiple_categories(self):
        other = Category.objects.create(name='Другое', slug='drugoe-test')
        request = self.request_factory.get(
            '/shop/catalog/',
            {'category': [self.category.slug, other.slug]},
        )
        self.assertIsNone(build_catalog_category_redirect(request))

    def test_category_page_with_brand_filter(self):
        brand = Brand.objects.create(name='BFilter', code='BF1', slug='bfilter-test')
        Product.objects.create(
            name='В бренде',
            slug='v-brende',
            code='CAT002',
            catalog_number='CAT002',
            category=self.category,
            brand=brand,
            in_stock=True,
            price=50,
        )
        url = reverse('shop:category', kwargs={'category_slug': self.category.slug})
        response = self.client.get(url, {'brand': brand.slug})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'В бренде')
