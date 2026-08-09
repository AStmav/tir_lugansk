import re

from django.db import migrations, models

DESCRIPTION_SECTION_RE = re.compile(r'для\s+(\d+)', re.IGNORECASE)
SLUG_CATEGORY_RE = re.compile(r'^category-(\d+)$', re.IGNORECASE)
SLUG_SUFFIX_RE = re.compile(r'-(\d{6,})$')


def _normalize(value):
    if not value:
        return ''
    s = str(value).strip().replace('[', '').replace(']', '').replace(';', '').strip()
    return s


def _extract_section_id(category):
    if category.description:
        match = DESCRIPTION_SECTION_RE.search(category.description)
        if match:
            return _normalize(match.group(1))
    slug = (category.slug or '').strip()
    match = SLUG_CATEGORY_RE.match(slug)
    if match:
        return _normalize(match.group(1))
    match = SLUG_SUFFIX_RE.search(slug)
    if match:
        return _normalize(match.group(1))
    return ''


def backfill_category_section_id(apps, schema_editor):
    Category = apps.get_model('shop', 'Category')
    claimed = set(
        Category.objects.exclude(section_id__isnull=True)
        .exclude(section_id='')
        .values_list('section_id', flat=True)
    )
    categories = list(Category.objects.all().order_by('id'))
    categories.sort(key=lambda c: (str(c.name or '').startswith('Категория '), c.id))

    updated = 0
    for category in categories:
        if category.section_id:
            claimed.add(category.section_id)
            continue
        section_id = _extract_section_id(category)
        if not section_id or section_id in claimed:
            continue
        Category.objects.filter(pk=category.pk).update(section_id=section_id)
        claimed.add(section_id)
        updated += 1

    if updated:
        print(f'✅ section_id заполнен у {updated} категорий')


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0023_warehouse_color'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='section_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='SECTION_ID из выгрузки 1С. Импорт номенклатуры ищет категорию по этому полю, не по URL.',
                max_length=50,
                null=True,
                unique=True,
                verbose_name='ID категории (1С)',
            ),
        ),
        migrations.RunPython(backfill_category_section_id, migrations.RunPython.noop),
    ]
