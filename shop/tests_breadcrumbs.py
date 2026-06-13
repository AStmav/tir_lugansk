from django.http import HttpRequest
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from shop.models import Category, Brand, Product


class BreadcrumbRenderTests(TestCase):
    def setUp(self):
        self.parent = Category.objects.create(
            name='Кабина/кузовное',
            slug='kabina-kuzovnoe-bc',
        )
        self.child = Category.objects.create(
            name='Зеркала',
            slug='zerkala-bc',
            parent=self.parent,
        )
        brand = Brand.objects.create(name='DEPO BC', code='DEPOBC', slug='depo-bc')
        self.product = Product.objects.create(
            name='Стекло зеркала 207*161*15 с подогревом',
            slug='product-mirror-bc',
            code='PED04BC',
            tmp_id='PED04BC',
            catalog_number='PED04BC',
            category=self.child,
            brand=brand,
            price=1000,
            stock_quantity=1,
            in_stock=True,
        )

    def tearDown(self):
        Product.objects.filter(slug='product-mirror-bc').delete()
        Brand.objects.filter(code='DEPOBC').delete()
        Category.objects.filter(slug='zerkala-bc').delete()
        Category.objects.filter(slug='kabina-kuzovnoe-bc').delete()

    def test_category_breadcrumb_chain(self):
        self.assertEqual(
            [c.name for c in self.child.get_breadcrumb_chain()],
            ['Кабина/кузовное', 'Зеркала'],
        )

    def test_render_breadcrumbs_horizontal_with_full_path(self):
        request = HttpRequest()
        request.META['SERVER_NAME'] = 'tir-lugansk.ru'
        request.META['SERVER_PORT'] = '443'

        tpl = Template(
            '{% load seo_tags %}{% render_breadcrumbs product=product %}'
        )
        html = tpl.render(Context({'request': request, 'product': self.product}))

        self.assertIn('class="product__breadcrumbs"', html)
        self.assertIn(f'<a href="{reverse("shop:catalog")}">Каталог</a>', html)
        self.assertIn(
            f'<a href="{self.parent.get_absolute_url()}">Кабина/кузовное</a>',
            html,
        )
        self.assertIn(
            f'<a href="{self.child.get_absolute_url()}">Зеркала</a>',
            html,
        )
        self.assertIn('<span> - </span>', html)
        self.assertNotIn('Главная', html)
        self.assertNotIn(self.product.name, html)
        self.assertNotIn('href="/catalog/"', html)
