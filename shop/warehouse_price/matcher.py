from typing import List, Optional, Tuple

from shop.models import Brand, OeKod, Product
from shop.warehouse_price.brand_aliases import (
    brand_from_normalized_index,
    brand_text_variants,
    brands_from_aliases,
    build_normalized_brand_index,
)
from shop.warehouse_price.prefixes import article_variants


class ProductMatcher:
    """
    Матчинг строки прайса → Product.

    Порядок:
    1) код 1С (tmp_id / code)
    2) бренд + артикул (± приставки) по номенклатуре
    3) бренд + артикул (± приставки) по OE (Аналог + Производитель)

    Производитель: точное имя/код → синонимы BrandAlias → варианты написания / нормализация.
    """

    def __init__(self, fixed_brand_id: Optional[int] = None):
        self.fixed_brand_id = fixed_brand_id
        self._norm_index = None

    def _normalized_index(self):
        if self._norm_index is None:
            self._norm_index = build_normalized_brand_index()
        return self._norm_index

    def resolve_brands(self, brand_text: str) -> List[Brand]:
        """Кандидаты бренда (без дублей), в стабильном порядке."""
        if self.fixed_brand_id:
            brand = Brand.objects.filter(pk=self.fixed_brand_id).first()
            return [brand] if brand else []

        text = (brand_text or '').strip()
        if not text:
            return []

        result: List[Brand] = []
        seen: set = set()

        def add(brand: Optional[Brand]) -> None:
            if brand and brand.id not in seen:
                seen.add(brand.id)
                result.append(brand)

        # 1) точное совпадение по code / name (и мягкие варианты дефиса/пробела)
        for variant in brand_text_variants(text):
            add(Brand.objects.filter(code__iexact=variant).first())
            add(Brand.objects.filter(name__iexact=variant).first())

        # 2) явные синонимы из админки
        for brand in brands_from_aliases(text):
            add(brand)

        # 3) нормализованный ключ (MERCEDESBENZ ↔ Mercedes Benz), если однозначен
        add(brand_from_normalized_index(text, self._normalized_index()))

        return result

    def resolve_brand(self, brand_text: str) -> Optional[Brand]:
        """Первый кандидат (обратная совместимость)."""
        brands = self.resolve_brands(brand_text)
        return brands[0] if brands else None

    def find_by_external_id(self, external_id: str) -> Tuple[Optional[Product], str]:
        code = (external_id or '').strip()
        if not code:
            return None, ''
        qs = Product.objects.filter(tmp_id=code)
        count = qs.count()
        if count == 1:
            return qs.first(), ''
        if count > 1:
            return None, 'неоднозначный код 1С (tmp_id)'
        qs = Product.objects.filter(code=code)
        count = qs.count()
        if count == 1:
            return qs.first(), ''
        if count > 1:
            return None, 'неоднозначный код 1С (code)'
        return None, ''

    def find_by_brand_article(self, brand: Brand, article: str) -> Tuple[Optional[Product], str]:
        variants = article_variants(brand, article)
        if not variants:
            return None, 'пустой артикул'

        candidates: List[Product] = list(
            Product.objects.filter(brand=brand, catalog_number_clean__in=variants)[:5]
        )
        if len(candidates) == 1:
            return candidates[0], ''
        if len(candidates) > 1:
            return None, 'неоднозначный артикул (каталожный)'

        candidates = list(
            Product.objects.filter(brand=brand, artikyl_number_clean__in=variants)[:5]
        )
        if len(candidates) == 1:
            return candidates[0], ''
        if len(candidates) > 1:
            return None, 'неоднозначный артикул (доп. номер)'
        return None, ''

    def find_by_oe(self, brand: Brand, article: str) -> Tuple[Optional[Product], str]:
        """Связка Аналог OE + Производитель (OeKod.brand)."""
        variants = article_variants(brand, article)
        if not variants:
            return None, 'пустой артикул'

        oe_rows = (
            OeKod.objects.filter(
                brand=brand,
                oe_kod_clean__in=variants,
                product_id__isnull=False,
            )
            .select_related('product')
            [:10]
        )
        product_ids = []
        products = []
        for oe in oe_rows:
            if oe.product_id and oe.product_id not in product_ids:
                product_ids.append(oe.product_id)
                products.append(oe.product)

        if len(products) == 1:
            return products[0], ''
        if len(products) > 1:
            return None, 'неоднозначный OE (несколько товаров)'
        return None, ''

    def match(
        self,
        article: str,
        brand_text: str = '',
        external_id: str = '',
    ) -> Tuple[Optional[Product], str]:
        product, reason = self.find_by_external_id(external_id)
        if product:
            return product, ''
        if reason:
            return None, reason

        brands = self.resolve_brands(brand_text)
        if not brands:
            return None, 'производитель не найден (укажите колонку производителя или фиксированный производитель)'

        last_reason = ''
        last_oe_reason = ''
        for brand in brands:
            product, reason = self.find_by_brand_article(brand, article)
            if product:
                return product, ''
            if reason and reason.startswith('неоднознач'):
                return None, reason
            last_reason = reason

            product, oe_reason = self.find_by_oe(brand, article)
            if product:
                return product, ''
            if oe_reason and oe_reason.startswith('неоднознач'):
                return None, oe_reason
            last_oe_reason = oe_reason

        return None, last_reason or last_oe_reason or 'товар не найден'
