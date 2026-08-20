"""Исправление опечаток и дубликатов в синонимах производителей (BrandAlias)."""
from django.core.management.base import BaseCommand
from django.db import transaction

from shop.models import BrandAlias

# Известные опечатки: (как сейчас в базе, как должно быть в прайсе)
KNOWN_ALIAS_FIXES = [
    ('DONFENG', 'DONGFENG'),
]


class Command(BaseCommand):
    help = (
        'Исправляет синонимы производителей: переименовывает alias или удаляет дубликат, '
        'если правильный alias уже есть. По умолчанию только просмотр (--apply для записи).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Сохранить изменения (по умолчанию только просмотр)',
        )
        parser.add_argument(
            '--from',
            dest='alias_from',
            type=str,
            default='',
            help='Текущее написание alias (например DONFENG)',
        )
        parser.add_argument(
            '--to',
            dest='alias_to',
            type=str,
            default='',
            help='Правильное написание alias (например DONGFENG)',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        alias_from = (options['alias_from'] or '').strip()
        alias_to = (options['alias_to'] or '').strip()

        if alias_from or alias_to:
            if not alias_from or not alias_to:
                self.stdout.write(self.style.ERROR('Укажите оба параметра: --from и --to'))
                return
            fixes = [(alias_from, alias_to)]
        else:
            fixes = list(KNOWN_ALIAS_FIXES)

        if not fixes:
            self.stdout.write('Нет правил для исправления.')
            return

        if not apply_changes:
            self.stdout.write(self.style.WARNING('Режим просмотра. Добавьте --apply для записи.'))

        stats = {'renamed': 0, 'removed': 0, 'skipped': 0}

        with transaction.atomic():
            for wrong, correct in fixes:
                self._fix_pair(wrong, correct, apply_changes, stats)

            if not apply_changes:
                transaction.set_rollback(True)

        self.stdout.write('')
        self.stdout.write(
            f'Готово: переименовано {stats["renamed"]}, удалено дубликатов {stats["removed"]}, '
            f'без изменений {stats["skipped"]}.'
        )

    def _fix_pair(self, wrong: str, correct: str, apply_changes: bool, stats: dict) -> None:
        rows = list(
            BrandAlias.objects.filter(alias__iexact=wrong).select_related('brand').order_by('id')
        )
        if not rows:
            self.stdout.write(f'  {wrong!r} → {correct!r}: записей не найдено')
            stats['skipped'] += 1
            return

        for row in rows:
            brand_name = row.brand.name if row.brand_id else '?'
            target = BrandAlias.objects.filter(
                brand_id=row.brand_id,
                alias__iexact=correct,
            ).exclude(pk=row.pk).first()

            if target:
                self.stdout.write(
                    f'  удалить {wrong!r} → {brand_name!r} '
                    f'(уже есть {correct!r})'
                )
                if apply_changes:
                    row.delete()
                stats['removed'] += 1
                continue

            self.stdout.write(f'  переименовать {wrong!r} → {correct!r} ({brand_name})')
            if apply_changes:
                row.alias = correct
                row.save(update_fields=['alias'])
            stats['renamed'] += 1
