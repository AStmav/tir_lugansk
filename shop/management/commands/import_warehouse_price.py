import os
import traceback

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from shop.models import Warehouse, WarehousePriceImport
from shop.warehouse_price.service import merge_import_settings, run_warehouse_price_import


class Command(BaseCommand):
    help = 'Импорт прайса поставщика в ProductOffer выбранного склада'

    def add_arguments(self, parser):
        parser.add_argument(
            '--price-import-id',
            type=int,
            default=None,
            help='ID записи WarehousePriceImport (фоновый импорт из админки)',
        )
        parser.add_argument('--warehouse-id', type=int, required=False)
        parser.add_argument('--file', type=str, required=False, help='Путь к .xlsx или .csv')
        parser.add_argument(
            '--use-warehouse-settings',
            action='store_true',
            help='Брать маппинг из warehouse.import_settings',
        )
        parser.add_argument('--header-row', type=int, default=None)
        parser.add_argument('--data-start-row', type=int, default=None)
        parser.add_argument('--col-article', type=str, default='')
        parser.add_argument('--col-brand', type=str, default='')
        parser.add_argument('--col-price', type=str, default='')
        parser.add_argument('--col-qty', type=str, default='')
        parser.add_argument('--col-external-id', type=str, default='')
        parser.add_argument('--fixed-brand-id', type=int, default=None)

    def handle(self, *args, **options):
        price_import_id = options.get('price_import_id')
        if price_import_id:
            return self._handle_price_import_record(price_import_id)

        warehouse_id = options.get('warehouse_id')
        file_path = options.get('file')
        if not warehouse_id or not file_path:
            raise CommandError(
                'Укажите --warehouse-id и --file или --price-import-id'
            )

        warehouse = Warehouse.objects.filter(pk=warehouse_id).first()
        if not warehouse:
            raise CommandError(f'Склад id={warehouse_id} не найден')

        if not os.path.isfile(file_path):
            raise CommandError(f'Файл не найден: {file_path}')

        import_settings = self._build_import_settings(warehouse, options)
        stats = run_warehouse_price_import(
            warehouse=warehouse,
            file_path=file_path,
            import_settings=import_settings,
        )
        self._print_stats(stats)

    def _handle_price_import_record(self, price_import_id: int) -> None:
        price_import = (
            WarehousePriceImport.objects.filter(pk=price_import_id)
            .select_related('warehouse')
            .first()
        )
        if not price_import:
            raise CommandError(f'Импорт прайса id={price_import_id} не найден')

        warehouse = price_import.warehouse
        file_path = getattr(price_import.file, 'path', None)
        if not file_path or not os.path.isfile(file_path):
            raise CommandError(f'Файл не найден: {file_path}')

        import_settings = price_import.import_settings or merge_import_settings(warehouse)
        if not import_settings.get('columns'):
            import_settings = merge_import_settings(warehouse)

        try:
            stats = run_warehouse_price_import(
                warehouse=warehouse,
                file_path=file_path,
                import_settings=import_settings,
                price_import=price_import,
            )
        except Exception as exc:
            price_import.status = WarehousePriceImport.STATUS_FAILED
            price_import.summary = str(exc)
            price_import.error_log = traceback.format_exc()
            price_import.processed_at = timezone.now()
            price_import.save(
                update_fields=['status', 'summary', 'error_log', 'processed_at']
            )
            raise CommandError(f'Ошибка импорта: {exc}') from exc

        self._print_stats(stats)

    def _build_import_settings(self, warehouse, options):
        if options['use_warehouse_settings']:
            return merge_import_settings(warehouse)

        columns = {}
        for key, opt in (
            ('article', 'col_article'),
            ('brand', 'col_brand'),
            ('price', 'col_price'),
            ('qty', 'col_qty'),
            ('external_id', 'col_external_id'),
        ):
            val = (options.get(opt) or '').strip()
            if val:
                columns[key] = val
        if not columns.get('article') or not columns.get('price'):
            merged = merge_import_settings(warehouse)
            if merged.get('columns'):
                return merged
            raise CommandError(
                'Укажите --col-article и --col-price или --use-warehouse-settings'
            )

        import_settings = {
            'header_row': options.get('header_row') or 1,
            'data_start_row': options.get('data_start_row') or 2,
            'columns': columns,
            'fixed_brand_id': options.get('fixed_brand_id'),
        }

        if options.get('header_row') is not None:
            import_settings['header_row'] = options['header_row']
        if options.get('data_start_row') is not None:
            import_settings['data_start_row'] = options['data_start_row']
        if options.get('fixed_brand_id') is not None:
            import_settings['fixed_brand_id'] = options['fixed_brand_id']
        return import_settings

    def _print_stats(self, stats) -> None:
        self.stdout.write(
            self.style.SUCCESS(
                f'Готово: строк {stats.total}, обновлено {stats.updated}, пропущено {stats.skipped}'
            )
        )
