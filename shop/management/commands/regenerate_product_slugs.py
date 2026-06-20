"""
Пересчёт slug товаров: артикул-бренд-название + алиасы для 301.

Примеры:
  python manage.py regenerate_product_slugs
  python manage.py regenerate_product_slugs --dry-run
  python manage.py regenerate_product_slugs --apply --limit 100
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from shop.models import Product, ProductSlugAlias
from shop.product_slugs import build_product_slug, uniquify_slug


class Command(BaseCommand):
    help = 'Пересчитать slug товаров и сохранить старые в ProductSlugAlias'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Записать изменения в БД',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только отчёт, без записи (режим по умолчанию)',
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
        if options['apply'] and options['dry_run']:
            raise CommandError('Укажите либо --apply, либо --dry-run, не оба сразу.')
        dry_run = not options['apply']
        limit = options['limit']
        batch_size = options['batch_size']

        if dry_run:
            self.stdout.write('Режим dry-run: изменения не сохраняются')

        slug_owners = self._load_slug_owners()
        stats = {
            'processed': 0,
            'unchanged': 0,
            'changed': 0,
            'aliases': 0,
        }
        examples = []
        planned_changes = []

        qs = Product.objects.select_related('brand').order_by('id')
        if limit:
            qs = qs[:limit]

        for product in qs.iterator(chunk_size=batch_size):
            stats['processed'] += 1
            old_slug = product.slug
            brand_name = product.brand.name if product.brand_id else ''
            product_pk = product.pk

            def is_taken(candidate, _pk=product_pk):
                owner = slug_owners.get(candidate)
                return owner is not None and owner != _pk

            base_slug = build_product_slug(
                product.catalog_number,
                brand_name,
                product.name,
            )
            new_slug = uniquify_slug(base_slug, is_taken)

            if new_slug == old_slug:
                stats['unchanged'] += 1
                continue

            stats['changed'] += 1
            if len(examples) < 5:
                examples.append(f'  {old_slug} → {new_slug}')

            slug_owners[new_slug] = product_pk
            planned_changes.append((product, old_slug, new_slug))

        if not dry_run:
            for offset in range(0, len(planned_changes), batch_size):
                batch = planned_changes[offset:offset + batch_size]
                self._apply_batch(batch, stats)

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

    def _load_slug_owners(self):
        """slug → pk товара (канонические slug + уже сохранённые алиасы)."""
        owners = dict(Product.objects.values_list('slug', 'pk'))
        for slug, product_id in ProductSlugAlias.objects.values_list('slug', 'product_id'):
            owners[slug] = product_id
        return owners

    @transaction.atomic
    def _apply_batch(self, batch, stats):
        """
        Двухфазная запись: сначала временные slug, потом финальные.
        Иначе bulk_update ломается, когда новый slug B совпадает со старым slug A в той же пачке.
        """
        seen_new_slugs = set()
        for product, old_slug, new_slug in batch:
            if new_slug in seen_new_slugs:
                raise CommandError(
                    f'Коллизия slug в пачке: {new_slug!r}. Прервите и сообщите разработчику.'
                )
            seen_new_slugs.add(new_slug)

        # Фаза 1: освобождаем уникальные slug (временные значения по pk).
        temp_products = []
        for product, old_slug, new_slug in batch:
            product.slug = f'_slug-migrate-{product.pk}'
            temp_products.append(product)
        Product.objects.bulk_update(temp_products, ['slug'])

        aliases = [
            ProductSlugAlias(slug=old_slug, product_id=product.pk)
            for product, old_slug, new_slug in batch
        ]
        if aliases:
            ProductSlugAlias.objects.bulk_create(
                aliases,
                ignore_conflicts=True,
            )
            stats['aliases'] += len(aliases)

        # Фаза 2: финальные slug (конфликтов в пачке уже нет).
        final_products = []
        for product, old_slug, new_slug in batch:
            product.slug = new_slug
            final_products.append(product)
        Product.objects.bulk_update(final_products, ['slug'])
