"""
Слияние дубликатов категорий с одинаковым SECTION_ID (1С).

Типичный случай: «BERGKRAFT» (section_id=000000001) и «Категория 000000001»
(slug category-000000001) после старого импорта по slug.

Запуск:
  python manage.py merge_duplicate_categories --dry-run
  python manage.py merge_duplicate_categories
"""
from django.core.management.base import BaseCommand

from shop.utils.category_merge import merge_all_duplicates


class Command(BaseCommand):
    help = 'Слить дубликаты категорий по SECTION_ID из 1С'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать план слияния, без изменений в БД',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        plans, totals = merge_all_duplicates(dry_run=dry_run)

        if not plans:
            self.stdout.write(self.style.SUCCESS('Дубликатов категорий не найдено.'))
            return

        self.stdout.write(
            f'Найдено групп дубликатов: {totals["groups"]}, '
            f'слияний: {len(plans)}'
        )
        for plan in plans:
            self.stdout.write(
                f'  [{plan.section_id}] '
                f'#{plan.duplicate.pk} «{plan.duplicate.name}» ({plan.duplicate.slug}) '
                f'→ #{plan.canonical.pk} «{plan.canonical.name}» ({plan.canonical.slug}) | '
                f'товаров: {plan.products}, '
                f'подкатегорий: {plan.child_categories}, '
                f'subcategories: {plan.subcategories}'
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\nРежим --dry-run: изменения не применены. '
                    'Запустите без --dry-run для слияния.'
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'\nГотово: слито категорий {totals["merged"]}, '
                f'перенесено товаров {totals["products"]}, '
                f'дочерних категорий {totals["child_categories"]}, '
                f'SubCategory {totals["subcategories"]}.'
            )
        )
