"""
Пересчёт slug товаров: артикул-бренд-название + алиасы для 301.

Примеры:
  python manage.py regenerate_product_slugs --dry-run
  python manage.py regenerate_product_slugs --apply --limit 100
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from shop.models import Product, ProductSlugAlias
from shop.product_slugs import build_product_slug, uniquify_slug


class Command(BaseCommand):
    help = 'Пересчитать slug товаров и сохранить старые в ProductSlugAlias'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Записать изменения (по умолчанию только отчёт)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Обработать не более N товаров (0 = все)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Размер пачки для bulk_update',
        )

    def handle(self, *args, **options):
        dry_run = not options['apply']
        limit = options['limit']
        batch_size = options['batch_size']

        if dry_run:
            self.stdout.write('Режим dry-run: изменения не сохраняются')

        reserved = set(Product.objects.values_list('slug', flat=True))
        reserved |= set(ProductSlugAlias.objects.values_list('slug', flat=True))

        stats = {
            'processed': 0,
            'unchanged': 0,
            'changed': 0,
            'aliases': 0,
        }
        examples = []
        to_update = []
        aliases_to_create = []

        qs = Product.objects.select_related('brand').order_by('id')
        if limit:
            qs = qs[:limit]

        for product in qs.iterator(chunk_size=batch_size):
            stats['processed'] += 1
            old_slug = product.slug
            brand_name = product.brand.name if product.brand_id else ''

            def is_taken(candidate, _old=old_slug, _pk=product.pk):
                if candidate == _old:
                    return False
                if candidate in reserved:
                    return True
                return Product.objects.filter(slug=candidate).exclude(pk=_pk).exists()

            new_slug = uniquify_slug(
                build_product_slug(product.catalog_number, brand_name, product.name),
                is_taken,
            )

            if new_slug == old_slug:
                stats['unchanged'] += 1
                continue

            stats['changed'] += 1
            if len(examples) < 5:
                examples.append(f'  {old_slug} → {new_slug}')

            if dry_run:
                reserved.add(new_slug)
                continue

            aliases_to_create.append(
                ProductSlugAlias(slug=old_slug, product_id=product.pk)
            )
            product.slug = new_slug
            reserved.add(new_slug)
            to_update.append(product)

            if len(to_update) >= batch_size:
                self._flush(to_update, aliases_to_create, stats)
                to_update = []
                aliases_to_create = []

        if not dry_run:
            self._flush(to_update, aliases_to_create, stats)

        self.stdout.write('')
        self.stdout.write(f"Обработано: {stats['processed']}")
        self.stdout.write(f"Без изменений: {stats['unchanged']}")
        self.stdout.write(f"Изменено slug: {stats['changed']}")
        if not dry_run:
            self.stdout.write(f"Создано алиасов: {stats['aliases']}")
        if examples:
            self.stdout.write('Примеры:')
            for line in examples:
                self.stdout.write(line)

    @transaction.atomic
    def _flush(self, products, aliases, stats):
        if aliases:
            ProductSlugAlias.objects.bulk_create(
                aliases,
                ignore_conflicts=True,
            )
            stats['aliases'] += len(aliases)
        if products:
            Product.objects.bulk_update(products, ['slug'])
