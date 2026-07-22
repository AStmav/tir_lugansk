import os

from django.core.management.base import BaseCommand, CommandError

from shop.models import Warehouse
from shop.warehouse_price.service import merge_import_settings, run_warehouse_price_import


class Command(BaseCommand):
    help = 'Импорт прайса поставщика в ProductOffer выбранного склада'

    def add_arguments(self, parser):
        parser.add_argument('--warehouse-id', type=int, required=True)
        parser.add_argument('--file', type=str, required=True, help='Путь к .xlsx или .csv')
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
        warehouse = Warehouse.objects.filter(pk=options['warehouse_id']).first()
        if not warehouse:
            raise CommandError(f'Склад id={options["warehouse_id"]} не найден')

        file_path = options['file']
        if not os.path.isfile(file_path):
            raise CommandError(f'Файл не найден: {file_path}')

        if options['use_warehouse_settings']:
            import_settings = merge_import_settings(warehouse)
        else:
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
                    import_settings = merged
                else:
                    raise CommandError(
                        'Укажите --col-article и --col-price или --use-warehouse-settings'
                    )
            else:
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

        stats = run_warehouse_price_import(
            warehouse=warehouse,
            file_path=file_path,
            import_settings=import_settings,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Готово: строк {stats.total}, обновлено {stats.updated}, пропущено {stats.skipped}'
            )
        )
