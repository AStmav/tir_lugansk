"""
Проверка и импорт изображений из incoming_images без таймаута Gunicorn.

Примеры:
  python manage.py import_incoming_images --check
  python manage.py import_incoming_images --check --product 110607100
  python manage.py import_incoming_images --product 000206631
  python manage.py import_incoming_images --batch-size 500
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from shop.models import ProductImage
from shop.utils.bulk_image_import import (
    collect_incoming_image_items,
    count_image_files,
    find_files_by_basename,
    find_product_by_key,
    get_incoming_images_dir,
    process_bulk_image_items,
    product_match_keys,
)


class Command(BaseCommand):
    help = 'Проверка и привязка изображений из incoming_images/'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Только проверить: сколько файлов в incoming/images и статус товара',
        )
        parser.add_argument(
            '--product',
            type=str,
            help='Код/tmp_id/каталожный номер (например 000206631 или 110607100)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Размер пачки при полном импорте (по умолчанию 500)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Обработать не более N файлов (для теста)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Перезаписывать существующие файлы в images/',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать план без изменений',
        )

    def handle(self, *args, **options):
        incoming_dir = get_incoming_images_dir()
        images_dir = settings.BASE_DIR / 'images'

        if options['check']:
            self._print_check(incoming_dir, images_dir, options.get('product'))
            return

        try:
            items = collect_incoming_image_items(
                incoming_dir,
                product_key=options.get('product'),
                limit=options.get('limit'),
            )
        except LookupError as exc:
            raise CommandError(str(exc)) from exc

        if not items:
            self.stdout.write(self.style.WARNING('Файлов для импорта не найдено.'))
            return

        self.stdout.write(f'Папка incoming: {incoming_dir}')
        self.stdout.write(f'К обработке: {len(items)} файлов')

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('Dry-run: изменений нет.'))
            for section_id, filename, path in items[:10]:
                self.stdout.write(f'  {section_id}/{filename}')
            if len(items) > 10:
                self.stdout.write(f'  ... и ещё {len(items) - 10}')
            return

        batch_size = max(1, options['batch_size'])
        totals = {
            'linked': 0,
            'restored': 0,
            'not_found': 0,
            'errors': 0,
            'skipped': 0,
            'invalid': 0,
        }

        for start in range(0, len(items), batch_size):
            chunk = items[start:start + batch_size]
            linked, not_found, errors, skipped, invalid, restored = process_bulk_image_items(
                chunk,
                remove_source_if_path=True,
                overwrite_existing=options['overwrite'],
            )
            totals['linked'] += linked
            totals['restored'] += restored
            totals['not_found'] += len(not_found)
            totals['errors'] += errors
            totals['skipped'] += skipped
            totals['invalid'] += invalid
            batch_num = start // batch_size + 1
            batch_total = (len(items) + batch_size - 1) // batch_size
            self.stdout.write(
                f'batch {batch_num}/{batch_total}: '
                f'linked={linked} restored={restored} skipped={skipped} '
                f'not_found={len(not_found)} errors={errors} invalid={invalid}'
            )

        self.stdout.write(self.style.SUCCESS(
            'Готово: '
            f"linked={totals['linked']}, restored={totals['restored']}, "
            f"skipped={totals['skipped']}, not_found={totals['not_found']}, "
            f"errors={totals['errors']}, invalid={totals['invalid']}"
        ))
        self.stdout.write(
            f"Осталось в incoming: {count_image_files(incoming_dir)} файлов"
        )

    def _print_check(self, incoming_dir, images_dir, product_key):
        incoming_count = count_image_files(incoming_dir)
        images_count = count_image_files(images_dir)

        self.stdout.write('=== Проверка изображений ===')
        self.stdout.write(f'incoming_images: {incoming_dir}')
        self.stdout.write(f'файлов в incoming: {incoming_count}')
        self.stdout.write(f'файлов в images/: {images_count}')

        if not product_key:
            return

        product = find_product_by_key(product_key)
        if not product:
            raise CommandError(f'Товар не найден: {product_key}')

        keys = sorted(product_match_keys(product))
        self.stdout.write('')
        self.stdout.write(f"Товар: {product.name}")
        self.stdout.write(f"code/tmp_id: {product.code} / {product.tmp_id}")
        self.stdout.write(f"каталожный номер: {product.catalog_number}")
        self.stdout.write(f"имена файлов для импорта: {', '.join(k + '.jpg' for k in keys if k)}")

        db_images = list(ProductImage.objects.filter(product=product).values_list('image', flat=True))
        self.stdout.write(f"записей в БД: {len(db_images)}")
        for path in db_images[:5]:
            self.stdout.write(f'  DB: {path}')

        for key in keys:
            if not key:
                continue
            incoming_matches = find_files_by_basename(incoming_dir, key)
            images_matches = find_files_by_basename(images_dir, key)
            self.stdout.write(f"incoming [{key}]: {len(incoming_matches)}")
            for path in incoming_matches[:5]:
                self.stdout.write(f'  {path}')
            self.stdout.write(f"images/ [{key}]: {len(images_matches)}")
            for path in images_matches[:5]:
                self.stdout.write(f'  {path}')
