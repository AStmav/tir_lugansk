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
            help='Размер пачки для записи',
        )

    def handle(self, *args, **options):
        if options['apply'] and options['dry_run']:
            raise CommandError('Укажите либо --apply, либо --dry-run, не оба сразу.')
        dry_run = not options['apply']
        limit = options['limit']
        batch_size = options['batch_size']

        if dry_run:
            self.stdout.write('Режим dry-run: изменения не сохраняются')

        reserved = self._load_reserved_slugs()
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

            new_slug = self._plan_new_slug(product, brand_name, old_slug, reserved)
            if new_slug is None:
                stats['unchanged'] += 1
                continue

            stats['changed'] += 1
            if len(examples) < 5:
                examples.append(f'  {old_slug} → {new_slug}')

            reserved.add(new_slug)
            planned_changes.append((product, old_slug, new_slug))

        planned_changes = self._ensure_globally_unique_planned(planned_changes)

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

    def _load_reserved_slugs(self):
        """Все занятые slug: канонические + алиасы."""
        reserved = set(Product.objects.values_list('slug', flat=True))
        reserved |= set(ProductSlugAlias.objects.values_list('slug', flat=True))
        return reserved

    def _slug_taken(self, candidate, product, old_slug, reserved):
        if candidate == old_slug:
            return False
        if candidate in reserved:
            return True
        return Product.objects.filter(slug=candidate).exclude(pk=product.pk).exists()

    def _plan_new_slug(self, product, brand_name, old_slug, reserved):
        """Подбирает новый slug или None, если менять не нужно."""
        product_pk = product.pk

        def is_taken(candidate, _old=old_slug, _product=product):
            return self._slug_taken(candidate, _product, _old, reserved)

        base_slug = build_product_slug(
            product.catalog_number,
            brand_name,
            product.name,
        )
        new_slug = uniquify_slug(base_slug, is_taken)
        if new_slug == old_slug:
            return None

        if self._slug_taken(new_slug, product, old_slug, reserved):
            new_slug = uniquify_slug(
                build_product_slug(
                    product.catalog_number,
                    brand_name,
                    product.name,
                    product.tmp_id or str(product_pk),
                ),
                is_taken,
            )
        if new_slug == old_slug:
            return None
        return new_slug

    def _ensure_globally_unique_planned(self, planned_changes):
        """
        Финальная проверка: два товара не могут получить один new_slug,
        и new_slug не может совпасть с чужим canonical в БД.
        """
        assigned = set()
        unique_changes = []

        for product, old_slug, new_slug in planned_changes:
            brand_name = product.brand.name if product.brand_id else ''
            candidate = new_slug

            def is_taken(c, _product=product):
                if c in assigned:
                    return True
                return Product.objects.filter(slug=c).exclude(pk=_product.pk).exists()

            if is_taken(candidate):
                candidate = uniquify_slug(
                    build_product_slug(
                        product.catalog_number,
                        brand_name,
                        product.name,
                        product.tmp_id or str(product.pk),
                    ),
                    is_taken,
                )
            if is_taken(candidate):
                candidate = uniquify_slug(
                    f'product-{product.pk}',
                    is_taken,
                )

            assigned.add(candidate)
            unique_changes.append((product, old_slug, candidate))

        return unique_changes

    @transaction.atomic
    def _apply_batch(self, batch, stats):
        """
        Двухфазная запись + по одному UPDATE на фазе 2
        (bulk_update может дать duplicate key при совпадении с чужим slug в БД).
        """
        seen_new_slugs = set()
        for product, old_slug, new_slug in batch:
            if new_slug in seen_new_slugs:
                raise CommandError(
                    f'Коллизия slug в пачке: {new_slug!r}. Прервите и сообщите разработчику.'
                )
            seen_new_slugs.add(new_slug)

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

        for product, old_slug, new_slug in batch:
            updated = Product.objects.filter(pk=product.pk).update(slug=new_slug)
            if not updated:
                raise CommandError(f'Не удалось обновить slug товара pk={product.pk}')
