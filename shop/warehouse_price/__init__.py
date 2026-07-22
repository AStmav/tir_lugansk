"""Импорт прайс-листа поставщика в ProductOffer конкретного склада."""

from shop.warehouse_price.service import run_warehouse_price_import

__all__ = ['run_warehouse_price_import']
