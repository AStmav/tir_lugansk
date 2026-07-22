"""
Отображение предложений товара по складам (Exist / ABCP стиль).

Поля Product.price / stock_quantity / in_stock пока остаются источником
для каталога; на карточке показываем ProductOffer, а при их отсутствии —
фолбэк в одну строку из полей Product.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from django.db.models import Prefetch


@dataclass
class OfferDisplay:
    warehouse_public: str
    warehouse_internal: str
    delivery_days: int
    delivery_label: str
    stock_quantity: int
    quantity_label: str
    price: Optional[Decimal]
    old_price: Optional[Decimal]
    is_legacy: bool = False


def format_delivery_days(days: int, *, in_stock: bool = True) -> str:
    """Подпись срока доставки для витрины."""
    if days is None:
        return 'Под заказ' if not in_stock else 'На складе'
    if days <= 0:
        return 'На складе' if in_stock else 'Сегодня'
    if days == 1:
        return '1 день'
    if days in (2, 3, 4):
        return f'{days} дня'
    return f'{days} дн.'


def format_quantity(quantity: int, *, available: bool = True) -> str:
    if not available:
        return '—'
    if quantity and quantity > 0:
        return f'{quantity} шт.'
    return '+'


def _legacy_offer(product) -> OfferDisplay:
    from shop.models import Warehouse

    warehouse = Warehouse.get_default()
    public = warehouse.name_public if warehouse else 'Склад'
    internal = warehouse.name_internal if warehouse else 'Основной'
    days = warehouse.delivery_days if warehouse else 0
    if not product.in_stock and (warehouse is None or warehouse.delivery_days == 0):
        # Сохраняем прежний смысл «Под заказ»
        delivery_label = 'Под заказ'
        days = days or 0
    else:
        delivery_label = format_delivery_days(days, in_stock=product.in_stock)

    qty = product.stock_quantity or 0
    price = product.price if product.price is not None else None
    return OfferDisplay(
        warehouse_public=public,
        warehouse_internal=internal,
        delivery_days=days,
        delivery_label=delivery_label,
        stock_quantity=qty,
        quantity_label=format_quantity(qty, available=product.in_stock),
        price=price,
        old_price=product.old_price,
        is_legacy=True,
    )


def offer_to_display(offer) -> OfferDisplay:
    days = offer.effective_delivery_days
    qty = offer.stock_quantity or 0
    available = qty > 0 or offer.price is not None
    return OfferDisplay(
        warehouse_public=offer.warehouse.name_public,
        warehouse_internal=offer.warehouse.name_internal,
        delivery_days=days,
        delivery_label=format_delivery_days(days, in_stock=qty > 0),
        stock_quantity=qty,
        quantity_label=format_quantity(qty, available=available),
        price=offer.price,
        old_price=offer.old_price,
        is_legacy=False,
    )


def active_offers_queryset(product=None):
    from shop.models import ProductOffer

    qs = (
        ProductOffer.objects.filter(is_active=True, warehouse__is_active=True)
        .select_related('warehouse')
        .order_by('warehouse__sort_order', 'price', 'id')
    )
    if product is not None:
        qs = qs.filter(product=product)
    return qs


def offers_prefetch():
    return Prefetch('offers', queryset=active_offers_queryset(), to_attr='_active_offers')


def get_product_display_offers(product) -> List[OfferDisplay]:
    """Список строк для таблицы на карточке товара."""
    cached = getattr(product, '_active_offers', None)
    if cached is not None:
        offers = list(cached)
    else:
        offers = list(active_offers_queryset(product))

    if offers:
        return [offer_to_display(o) for o in offers]
    return [_legacy_offer(product)]
