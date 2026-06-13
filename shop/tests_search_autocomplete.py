"""
Тесты подсказок поиска (search_autocomplete).
Проверка требований заказчика: по номерам — по умолчанию только по началу; с % — и в середине.
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from shop.models import Product, Category, Brand
from shop.views import _parse_search_mode, _normalize_search_mode, _parse_search_pick


class ParseSearchModeTests(TestCase):
    """Парсинг режима поиска: % даёт поиск в середине."""

    def test_normalize_search_mode_defaults_to_code(self):
        self.assertEqual(_normalize_search_mode(''), 'code')
        self.assertEqual(_normalize_search_mode(None), 'code')
        self.assertEqual(_normalize_search_mode('invalid'), 'code')

    def test_empty_returns_false(self):
        stripped, allow = _parse_search_mode('')
        self.assertEqual(stripped, '')
        self.assertFalse(allow)

    def test_no_percent_returns_false(self):
        stripped, allow = _parse_search_mode('02095')
        self.assertEqual(stripped, '02095')
        self.assertFalse(allow)

    def test_percent_in_query_returns_true(self):
        stripped, allow = _parse_search_mode('%02095')
        self.assertEqual(stripped, '02095')
        self.assertTrue(allow)

    def test_percent_suffix(self):
        stripped, allow = _parse_search_mode('02095%')
        self.assertEqual(stripped, '02095')
        self.assertTrue(allow)

    def test_percent_stripped_and_trimmed(self):
        stripped, allow = _parse_search_mode('  % 02095 %  ')
        self.assertEqual(stripped, '02095')
        self.assertTrue(allow)


class SearchAutocompleteBehaviorTests(TestCase):
    """
    Поведение подсказок по требованиям заказчика:
    - Без %: по номерам только «начинается с» / точное совпадение.
    - С %: по номерам ещё и «содержит».
    - По названию всегда по подстроке.
    """

    def setUp(self):
        self.client = Client()
        cat = Category.objects.create(name='ТестКат', slug='test-cat-autocomplete')
        self.brand = Brand.objects.create(name='ТестБренд', code='TBAUTO')
        # Товар, номер которого начинается с 02095
        self.prefix_product = Product.objects.create(
            name='Товар по началу номера',
            slug='product-prefix-02095',
            code='02095123',
            tmp_id='02095123',
            catalog_number='02095123',
            artikyl_number='',
            category=cat,
            brand=self.brand,
            price=100,
            stock_quantity=1,
            in_stock=True,
        )
        # Товар, номер которого содержит 02095 в середине (не в начале)
        self.middle_product = Product.objects.create(
            name='Товар номер в середине',
            slug='product-middle-bk1202095',
            code='BK1202095AS',
            tmp_id='BK1202095AS',
            catalog_number='BK1202095AS',
            artikyl_number='',
            category=cat,
            brand=self.brand,
            price=200,
            stock_quantity=1,
            in_stock=True,
        )
        # Товар по названию (для проверки поиска по имени)
        self.name_product = Product.objects.create(
            name='Сальник рулевой',
            slug='product-salnik',
            code='SAL001',
            tmp_id='SAL001',
            catalog_number='SAL001',
            artikyl_number='',
            category=cat,
            brand=self.brand,
            price=50,
            stock_quantity=1,
            in_stock=True,
        )

    def tearDown(self):
        Product.objects.filter(slug__startswith='product-').delete()
        Brand.objects.filter(code='TBAUTO').delete()
        Category.objects.filter(slug='test-cat-autocomplete').delete()

    def _suggestion_values(self, q):
        """GET /search-autocomplete/?q=... и множество value из ответа."""
        params = {'q': q}
        # Историческая логика этого набора тестов проверяет номерной сценарий.
        # После введения search_mode явно фиксируем режим "по коду".
        if any(ch.isdigit() or ch == '%' for ch in q):
            params['search_mode'] = 'code'
        else:
            params['search_mode'] = 'name'
        resp = self.client.get(reverse('shop:search_autocomplete'), params)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('suggestions', data)
        return {s['value'] for s in data['suggestions']}

    def test_short_query_returns_empty(self):
        resp = self.client.get(reverse('shop:search_autocomplete'), {'q': '0'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'suggestions': []})

    def test_without_percent_prefix_match_in_suggestions(self):
        """Запрос 02095 без %: в подсказках только товар, у которого номер начинается с 02095."""
        values = self._suggestion_values('02095')
        self.assertIn(
            self.prefix_product.catalog_number,
            values,
            'Товар с номером 02095123 (начало 02095) должен быть в подсказках',
        )
        self.assertNotIn(
            self.middle_product.catalog_number,
            values,
            'Товар BK1202095AS (02095 в середине) не должен быть в подсказках без %',
        )

    def test_with_percent_contains_match_in_suggestions(self):
        """Запрос %02095: в подсказках и товар с 02095 в середине номера."""
        values = self._suggestion_values('%02095')
        self.assertIn(
            self.prefix_product.catalog_number,
            values,
            'Товар 02095123 должен быть в подсказках и при поиске с %',
        )
        self.assertIn(
            self.middle_product.catalog_number,
            values,
            'Товар BK1202095AS (02095 в середине) должен быть в подсказках при %02095',
        )

    def test_name_search_always_substring(self):
        """Поиск по названию: подсказки по подстроке (без %)."""
        # Подстрока «рулевой» в названии «Сальник рулевой»
        values = self._suggestion_values('рулевой')
        self.assertIn(
            self.name_product.catalog_number,
            values,
            'Товар «Сальник рулевой» должен находиться по запросу «рулевой»',
        )


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class SearchModeSeparationTests(TestCase):
    """Проверка разделения режимов поиска: name vs code."""

    def setUp(self):
        self.client = Client()
        cat = Category.objects.create(name='ТестКат2', slug='test-cat-search-mode')
        brand = Brand.objects.create(name='ТестБренд2', code='TBMODE')

        # Совпадает только по НАЗВАНИЮ
        self.name_only_product = Product.objects.create(
            name='Амортизатор 12345',
            slug='product-name-only-12345',
            code='NAMEONLY001',
            tmp_id='NAMEONLY001',
            catalog_number='NX-001',
            artikyl_number='',
            category=cat,
            brand=brand,
            price=100,
            stock_quantity=1,
            in_stock=True,
        )
        # Совпадает только по КОДУ
        self.code_only_product = Product.objects.create(
            name='Обычный товар',
            slug='product-code-only-12345',
            code='CODE-ONLY-1',
            tmp_id='CODE-ONLY-1',
            catalog_number='12345',
            artikyl_number='',
            category=cat,
            brand=brand,
            price=120,
            stock_quantity=1,
            in_stock=True,
        )

    def tearDown(self):
        Product.objects.filter(slug__in=['product-name-only-12345', 'product-code-only-12345']).delete()
        Brand.objects.filter(code='TBMODE').delete()
        Category.objects.filter(slug='test-cat-search-mode').delete()

    def test_autocomplete_name_mode_ignores_code_matches(self):
        resp = self.client.get(
            reverse('shop:search_autocomplete'),
            {'q': '12345', 'search_mode': 'name'},
        )
        self.assertEqual(resp.status_code, 200)
        values = {s['value'] for s in resp.json().get('suggestions', [])}
        self.assertIn(self.name_only_product.catalog_number, values)
        self.assertNotIn(self.code_only_product.catalog_number, values)

    def test_autocomplete_code_mode_ignores_name_matches(self):
        resp = self.client.get(
            reverse('shop:search_autocomplete'),
            {'q': '12345', 'search_mode': 'code'},
        )
        self.assertEqual(resp.status_code, 200)
        values = {s['value'] for s in resp.json().get('suggestions', [])}
        self.assertIn(self.code_only_product.catalog_number, values)
        self.assertNotIn(self.name_only_product.catalog_number, values)

    def test_catalog_name_mode_returns_only_name_matches(self):
        resp = self.client.get(
            reverse('shop:catalog'),
            {'search': '12345', 'search_mode': 'name'},
        )
        self.assertEqual(resp.status_code, 200)
        products = list(resp.context['products'])
        product_ids = {p.id for p in products}
        self.assertIn(self.name_only_product.id, product_ids)
        self.assertNotIn(self.code_only_product.id, product_ids)

    def test_catalog_code_mode_returns_only_code_matches(self):
        resp = self.client.get(
            reverse('shop:catalog'),
            {'search': '12345', 'search_mode': 'code'},
        )
        self.assertEqual(resp.status_code, 200)
        products = list(resp.context['products'])
        product_ids = {p.id for p in products}
        self.assertIn(self.code_only_product.id, product_ids)
        self.assertNotIn(self.name_only_product.id, product_ids)

    def test_catalog_without_search_mode_defaults_to_code(self):
        """Без search_mode в URL используется режим по коду (как в форме по умолчанию)."""
        resp = self.client.get(reverse('shop:catalog'), {'search': '12345'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['search_mode'], 'code')
        product_ids = {p.id for p in resp.context['products']}
        self.assertIn(self.code_only_product.id, product_ids)
        self.assertNotIn(self.name_only_product.id, product_ids)

    def test_name_mode_finds_by_applicability(self):
        cat = Category.objects.get(slug='test-cat-search-mode')
        brand = Brand.objects.get(code='TBMODE')
        p = Product.objects.create(
            name='Деталь без марки в названии',
            slug='product-applicability-volvo',
            code='APP-VOLVO-1',
            tmp_id='APP-VOLVO-1',
            catalog_number='APP-001',
            artikyl_number='',
            applicability='Volvo FH12, задняя ось',
            category=cat,
            brand=brand,
            price=80,
            stock_quantity=1,
            in_stock=True,
        )
        try:
            resp = self.client.get(
                reverse('shop:catalog'),
                {'search': 'Volvo FH12', 'search_mode': 'name'},
            )
            self.assertEqual(resp.status_code, 200)
            product_ids = {x.id for x in resp.context['products']}
            self.assertIn(p.id, product_ids)
        finally:
            Product.objects.filter(slug='product-applicability-volvo').delete()


class ParseSearchPickTests(TestCase):
    def test_valid_id(self):
        self.assertEqual(_parse_search_pick('42'), 42)

    def test_invalid_values(self):
        self.assertIsNone(_parse_search_pick(''))
        self.assertIsNone(_parse_search_pick(None))
        self.assertIsNone(_parse_search_pick('abc'))
        self.assertIsNone(_parse_search_pick('0'))
        self.assertIsNone(_parse_search_pick('-1'))


class SearchPickBehaviorTests(TestCase):
    """Точный выбор из подсказки: search_pick показывает только выбранный товар."""

    def setUp(self):
        self.client = Client()
        cat = Category.objects.create(name='ТестКатPick', slug='test-cat-search-pick')
        self.brand_wing = Brand.objects.create(
            name='Kahveci Pick Test', code='KAHVPICK', slug='kahveci-pick-test',
        )
        self.brand_oil = Brand.objects.create(
            name='Ravenol Pick Test', code='RAVPICK', slug='ravenol-pick-test',
        )

        self.wing_product = Product.objects.create(
            name='Крыло заднее (средняя часть)',
            slug='product-wing-1212108',
            code='WING-12108',
            tmp_id='WING-12108',
            catalog_number='12.12108',
            artikyl_number='',
            category=cat,
            brand=self.brand_wing,
            price=5000,
            stock_quantity=1,
            in_stock=True,
        )
        self.oil_product = Product.objects.create(
            name='Масло ATF Ravenol ULV-D-M',
            slug='product-oil-1212108',
            code='OIL-12108',
            tmp_id='OIL-12108',
            catalog_number='121210800401999',
            artikyl_number='',
            category=cat,
            brand=self.brand_oil,
            price=1200,
            stock_quantity=1,
            in_stock=True,
        )

    def tearDown(self):
        Product.objects.filter(slug__in=['product-wing-1212108', 'product-oil-1212108']).delete()
        Brand.objects.filter(code__in=['KAHVPICK', 'RAVPICK']).delete()
        Category.objects.filter(slug='test-cat-search-pick').delete()

    def test_autocomplete_returns_product_id(self):
        resp = self.client.get(
            reverse('shop:search_autocomplete'),
            {'q': '12.12108', 'search_mode': 'code'},
        )
        self.assertEqual(resp.status_code, 200)
        suggestions = resp.json().get('suggestions', [])
        by_value = {s['value']: s for s in suggestions}
        self.assertEqual(by_value['12.12108']['product_id'], self.wing_product.id)
        self.assertEqual(by_value['121210800401999']['product_id'], self.oil_product.id)

    def test_broad_search_without_pick_returns_multiple(self):
        resp = self.client.get(
            reverse('shop:catalog'),
            {'search': '12.12108', 'search_mode': 'code'},
        )
        self.assertEqual(resp.status_code, 200)
        product_ids = {p.id for p in resp.context['products']}
        self.assertIn(self.wing_product.id, product_ids)
        self.assertIn(self.oil_product.id, product_ids)

    def test_search_pick_returns_only_selected_product(self):
        resp = self.client.get(
            reverse('shop:catalog'),
            {
                'search': '12.12108',
                'search_mode': 'code',
                'search_pick': self.wing_product.id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        product_ids = {p.id for p in resp.context['products']}
        self.assertEqual(product_ids, {self.wing_product.id})

    def test_search_pick_for_oil_returns_only_oil(self):
        resp = self.client.get(
            reverse('shop:catalog'),
            {
                'search': '12.12108',
                'search_mode': 'code',
                'search_pick': self.oil_product.id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        product_ids = {p.id for p in resp.context['products']}
        self.assertEqual(product_ids, {self.oil_product.id})

    def test_invalid_search_pick_falls_back_to_broad_search(self):
        resp = self.client.get(
            reverse('shop:catalog'),
            {
                'search': '12.12108',
                'search_mode': 'code',
                'search_pick': 999999999,
            },
        )
        self.assertEqual(resp.status_code, 200)
        product_ids = {p.id for p in resp.context['products']}
        self.assertIn(self.wing_product.id, product_ids)
        self.assertIn(self.oil_product.id, product_ids)
