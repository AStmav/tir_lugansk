from django.db import migrations, models
import django.db.models.deletion


SEED_ALIASES = [
    # (alias_as_in_price, catalog_brand_name)
    ('Cummins Ch', 'Cummins'),
    ('MERCEDES-BENZ', 'Mercedes Benz'),
    ('Mercedes-Benz', 'Mercedes Benz'),
    ('ПАЗ', 'PAZ'),
    ('УАЗ', 'UAZ'),
    ('АВТОДИЗЕЛЬ ЯМЗ', 'ЯМЗ'),
    ('ENTERPRISE Original', 'ENTERPRISE'),
    ('Hyundai/KIA', 'HYUNDAI'),
    ('Hyundai/KIA', 'KIA'),
]


def seed_brand_aliases(apps, schema_editor):
    Brand = apps.get_model('shop', 'Brand')
    BrandAlias = apps.get_model('shop', 'BrandAlias')
    for alias, brand_name in SEED_ALIASES:
        brand = Brand.objects.filter(name__iexact=brand_name).first()
        if not brand:
            continue
        BrandAlias.objects.get_or_create(brand=brand, alias=alias)


def unseed_brand_aliases(apps, schema_editor):
    BrandAlias = apps.get_model('shop', 'BrandAlias')
    aliases = [a for a, _ in SEED_ALIASES]
    BrandAlias.objects.filter(alias__in=aliases).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0021_warehouse_markup'),
    ]

    operations = [
        migrations.CreateModel(
            name='BrandAlias',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'alias',
                    models.CharField(
                        help_text='Написание бренда в файле поставщика (без учёта регистра)',
                        max_length=255,
                        verbose_name='Как в прайсе',
                    ),
                ),
                (
                    'brand',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='aliases',
                        to='shop.brand',
                        verbose_name='Бренд в каталоге',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Синоним бренда',
                'verbose_name_plural': 'Синонимы брендов',
                'ordering': ['alias', 'brand__name'],
            },
        ),
        migrations.AddIndex(
            model_name='brandalias',
            index=models.Index(fields=['alias'], name='shop_brandalias_alias_idx'),
        ),
        migrations.AddConstraint(
            model_name='brandalias',
            constraint=models.UniqueConstraint(
                fields=('brand', 'alias'),
                name='shop_brandalias_brand_alias_uniq',
            ),
        ),
        migrations.RunPython(seed_brand_aliases, unseed_brand_aliases),
    ]
