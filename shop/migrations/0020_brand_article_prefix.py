from django.db import migrations, models
import django.db.models.deletion


# Имя бренда (как может быть в 1С) → приставки
SEED_PREFIXES = [
    ('SE-M', ['SEM']),
    ('SEM', ['SEM']),
    ('Auger', ['AUG']),
    ('Universal Components', ['UCA']),
    ('M-Filter', ['MFA', 'MF']),
    ('Lema', ['LE']),
    ('Dinex', ['DIN']),
]


def seed_brand_prefixes(apps, schema_editor):
    Brand = apps.get_model('shop', 'Brand')
    BrandArticlePrefix = apps.get_model('shop', 'BrandArticlePrefix')
    for brand_name, prefixes in SEED_PREFIXES:
        brand = Brand.objects.filter(name__iexact=brand_name).first()
        if not brand:
            continue
        for prefix in prefixes:
            BrandArticlePrefix.objects.get_or_create(
                brand=brand,
                prefix=prefix.upper(),
            )


def unseed_brand_prefixes(apps, schema_editor):
    BrandArticlePrefix = apps.get_model('shop', 'BrandArticlePrefix')
    BrandArticlePrefix.objects.filter(
        prefix__in=['SEM', 'AUG', 'UCA', 'MFA', 'MF', 'LE', 'DIN']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0019_warehouse_price_import'),
    ]

    operations = [
        migrations.CreateModel(
            name='BrandArticlePrefix',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefix', models.CharField(
                    help_text='Буквы/цифры без пробелов, например SEM, AUG, DIN',
                    max_length=32,
                    verbose_name='Приставка',
                )),
                ('brand', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='article_prefixes',
                    to='shop.brand',
                    verbose_name='Бренд',
                )),
            ],
            options={
                'verbose_name': 'Приставка артикула',
                'verbose_name_plural': 'Приставки артикулов',
                'ordering': ['brand__name', 'prefix'],
            },
        ),
        migrations.AddConstraint(
            model_name='brandarticleprefix',
            constraint=models.UniqueConstraint(
                fields=('brand', 'prefix'),
                name='shop_brandarticleprefix_brand_prefix_uniq',
            ),
        ),
        migrations.RunPython(seed_brand_prefixes, unseed_brand_prefixes),
    ]
