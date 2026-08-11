"""
Слияние дубликатов категорий с одинаковым SECTION_ID (1С).

Типичный случай: «BERGKRAFT» (section_id=000000001) и «Категория 000000001»
(slug category-000000001) после старого импорта по slug.

Одиночные авто-категории (без пары) merge не трогает — см. --orphans и --map.

Запуск:
  python manage.py merge_duplicate_categories --dry-run
  python manage.py merge_duplicate_categories
  python manage.py merge_duplicate_categories --orphans
  python manage.py merge_duplicate_categories --map 000022160:selhoz-tehnika --dry-run
  python manage.py merge_duplicate_categories --map 000022160:selhoz-tehnika
  python manage.py merge_duplicate_categories --delete-empty-orphans
"""
from django.core.management.base import BaseCommand, CommandError

from shop.utils.category_merge import (
    cleanup_orphan_auto_categories,
    find_orphan_auto_categories,
    map_orphan_auto_category,
    merge_all_duplicates,
)


class Command(BaseCommand):
    help = 'Слить дубликаты категорий по SECTION_ID из 1С'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать план, без изменений в БД',
        )
        parser.add_argument(
            '--orphans',
            action='store_true',
            help='Показать одиночные авто-категории (без пары для merge)',
        )
        parser.add_argument(
            '--map',
            action='append',
            default=[],
            metavar='SECTION_ID:slug',
            help='Привязать SECTION_ID к категории и слить авто-категорию (можно повторять)',
        )
        parser.add_argument(
            '--delete-empty-orphans',
            action='store_true',
            help='Удалить одиночные авто-категории без товаров и дочерних записей',
        )
        parser.add_argument(
            '--deactivate-orphans',
            action='store_true',
            help='Скрыть одиночные авто-категории из меню (is_active=False)',
        )
        parser.add_argument(
            '--skip-merge',
            action='store_true',
            help='Не выполнять слияние пар дубликатов, только операции с orphans/map',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        ran_something = False

        if not options['skip_merge'] and not options['map']:
            ran_something = True
            self._run_pair_merge(dry_run)

        if options['orphans'] or options['delete_empty_orphans'] or options['deactivate_orphans']:
            ran_something = True
            self._run_orphan_actions(options, dry_run)

        for mapping in options['map']:
            ran_something = True
            self._run_map(mapping, dry_run)

        if not ran_something:
            self._run_pair_merge(dry_run)
            self._run_orphan_actions({'orphans': True}, dry_run=True)

    def _run_pair_merge(self, dry_run):
        plans, totals = merge_all_duplicates(dry_run=dry_run)

        if not plans:
            self.stdout.write(self.style.SUCCESS('Пар дубликатов не найдено.'))
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
                self.style.WARNING('Режим --dry-run: слияние пар не выполнено.')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'Слито категорий {totals["merged"]}, '
                f'перенесено товаров {totals["products"]}, '
                f'дочерних категорий {totals["child_categories"]}, '
                f'SubCategory {totals["subcategories"]}.'
            )
        )

    def _run_orphan_actions(self, options, dry_run):
        orphans = find_orphan_auto_categories()
        if options.get('orphans') or dry_run:
            if not orphans:
                self.stdout.write(self.style.SUCCESS('Одиночных авто-категорий не найдено.'))
            else:
                self.stdout.write(f'Одиночных авто-категорий: {len(orphans)}')
                for item in orphans:
                    self.stdout.write(
                        f'  [{item.section_id}] '
                        f'#{item.category.pk} «{item.category.name}» ({item.category.slug}) | '
                        f'товаров: {item.products}, '
                        f'дочерних: {item.child_categories}, '
                        f'subcategories: {item.subcategories}'
                    )
                self.stdout.write(
                    'Подсказка: привязать к нормальной категории — '
                    '--map SECTION_ID:slug (например --map 000022160:selhoz-tehnika)'
                )

        if options.get('delete_empty_orphans') or options.get('deactivate_orphans'):
            totals = cleanup_orphan_auto_categories(
                dry_run=dry_run,
                delete_empty=options.get('delete_empty_orphans'),
                deactivate=options.get('deactivate_orphans'),
            )
            if dry_run:
                self.stdout.write(
                    self.style.WARNING('Режим --dry-run: очистка orphans не выполнена.')
                )
                return
            if options.get('delete_empty_orphans'):
                self.stdout.write(self.style.SUCCESS(f'Удалено пустых авто-категорий: {totals["deleted"]}'))
            if options.get('deactivate_orphans'):
                self.stdout.write(self.style.SUCCESS(f'Деактивировано авто-категорий: {totals["deactivated"]}'))

    def _run_map(self, mapping, dry_run):
        if ':' not in mapping:
            raise CommandError(f'Неверный формат --map: {mapping!r}. Ожидается SECTION_ID:slug')
        section_id, target_slug = mapping.split(':', 1)
        section_id = section_id.strip()
        target_slug = target_slug.strip()
        if not section_id or not target_slug:
            raise CommandError(f'Неверный формат --map: {mapping!r}')

        try:
            plan = map_orphan_auto_category(section_id, target_slug, dry_run=dry_run)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f'[{plan.section_id}] '
            f'#{plan.orphan.pk} «{plan.orphan.name}» ({plan.orphan.slug}) '
            f'→ #{plan.target.pk} «{plan.target.name}» ({plan.target.slug}) | '
            f'товаров: {plan.products}'
        )
        if dry_run:
            self.stdout.write(self.style.WARNING('Режим --dry-run: привязка не выполнена.'))
        else:
            self.stdout.write(self.style.SUCCESS('Привязка и слияние выполнены.'))
