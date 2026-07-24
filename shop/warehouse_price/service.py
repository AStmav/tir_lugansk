from django.db import transaction
from django.db.models import Min, Sum
from django.utils import timezone

from shop.models import Product, ProductOffer, Warehouse, WarehousePriceImport
from shop.warehouse_price.markup import try_apply_markup
from shop.warehouse_price.matcher import ProductMatcher
from shop.warehouse_price.parser import iter_price_rows
from shop.warehouse_price.types import DEFAULT_IMPORT_SETTINGS, ImportStats, RowSkip


def sync_product_from_offers(product_id: int) -> None:
    """
    Снимок для каталога/поиска: min-цена и суммарный остаток по активным офферам.
    Карточка товара по-прежнему читает ProductOffer напрямую.
    """
    agg = ProductOffer.objects.filter(
        product_id=product_id,
        is_active=True,
        warehouse__is_active=True,
    ).aggregate(
        min_price=Min('price'),
        total_qty=Sum('stock_quantity'),
    )
    total_qty = int(agg['total_qty'] or 0)
    fields = {
        'stock_quantity': total_qty,
        'in_stock': total_qty > 0,
    }
    if agg['min_price'] is not None:
        fields['price'] = agg['min_price']
    Product.objects.filter(pk=product_id).update(**fields)


def merge_import_settings(warehouse: Warehouse) -> dict:
    settings = dict(DEFAULT_IMPORT_SETTINGS)
    if warehouse.import_settings:
        settings.update(warehouse.import_settings)
    columns = dict(DEFAULT_IMPORT_SETTINGS.get('columns') or {})
    columns.update((warehouse.import_settings or {}).get('columns') or {})
    settings['columns'] = columns
    return settings


def run_warehouse_price_import(
    warehouse: Warehouse,
    file_path: str,
    import_settings: dict = None,
    price_import: WarehousePriceImport = None,
) -> ImportStats:
    settings = merge_import_settings(warehouse)
    if import_settings:
        merged = dict(settings)
        merged.update(import_settings)
        if 'columns' in import_settings:
            cols = dict(settings.get('columns') or {})
            cols.update(import_settings['columns'] or {})
            merged['columns'] = cols
        settings = merged

    header_row = int(settings.get('header_row') or 1)
    data_start_row = int(settings.get('data_start_row') or 2)
    column_map = settings.get('columns') or {}
    fixed_brand_id = settings.get('fixed_brand_id')

    stats = ImportStats()
    matcher = ProductMatcher(fixed_brand_id=fixed_brand_id)
    touched_product_ids = set()

    # Prefetch ranges once for markup_mode=ranges
    if warehouse.markup_mode == Warehouse.MARKUP_RANGES:
        list(warehouse.markup_ranges.all())

    for row in iter_price_rows(file_path, header_row, data_start_row, column_map):
        stats.total += 1
        product, reason = matcher.match(
            article=row.article,
            brand_text=row.brand,
            external_id=row.external_id,
        )
        if not product:
            stats.skipped += 1
            stats.errors.append(
                RowSkip(
                    row_number=row.row_number,
                    reason=reason or 'не найдено',
                    article=row.article,
                    brand=row.brand,
                )
            )
            continue

        sell_price, markup_error = try_apply_markup(warehouse, row.price)
        if sell_price is None:
            stats.skipped += 1
            stats.errors.append(
                RowSkip(
                    row_number=row.row_number,
                    reason=markup_error or 'ошибка наценки',
                    article=row.article,
                    brand=row.brand,
                )
            )
            continue

        ProductOffer.objects.update_or_create(
            product=product,
            warehouse=warehouse,
            defaults={
                'price': sell_price,
                'stock_quantity': row.quantity,
                'is_active': True,
            },
        )
        touched_product_ids.add(product.pk)
        stats.updated += 1

    for product_id in touched_product_ids:
        sync_product_from_offers(product_id)

    warehouse.last_uploaded_at = timezone.now()
    warehouse.save(update_fields=['last_uploaded_at', 'updated_at'])

    if price_import:
        price_import.total_rows = stats.total
        price_import.updated_rows = stats.updated
        price_import.skipped_rows = stats.skipped
        price_import.error_count = len(stats.errors)
        price_import.status = WarehousePriceImport.STATUS_COMPLETED
        price_import.summary = _format_summary(stats)
        price_import.error_log = _format_error_log(stats.errors)
        price_import.processed_at = timezone.now()
        price_import.save()

    return stats


def _format_summary(stats: ImportStats) -> str:
    return (
        f'Строк прайса: {stats.total}; обновлено предложений: {stats.updated}; '
        f'пропущено: {stats.skipped}'
    )


def _format_error_log(errors) -> str:
    if not errors:
        return ''
    lines = ['row;article;brand;reason']
    for err in errors[:5000]:
        lines.append(
            f'{err.row_number};{err.article};{err.brand};{err.reason}'
        )
    if len(errors) > 5000:
        lines.append(f'... и ещё {len(errors) - 5000} строк')
    return '\n'.join(lines)


@transaction.atomic
def run_warehouse_price_import_atomic(*args, **kwargs):
    return run_warehouse_price_import(*args, **kwargs)
