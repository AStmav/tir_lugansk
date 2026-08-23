from django.db import migrations


def seed_brand_aliases(apps, schema_editor):
    Brand = apps.get_model('shop', 'Brand')
    BrandAlias = apps.get_model('shop', 'BrandAlias')

    pairs = [
        ('КамАЗ', 'KAMAZ'),
        ('KS', 'Kolbenschmidt'),
    ]
    for alias, brand_name in pairs:
        brand = Brand.objects.filter(name__iexact=brand_name).first()
        if not brand:
            continue
        BrandAlias.objects.get_or_create(
            brand_id=brand.id,
            alias=alias,
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0027_delivery_days_range'),
    ]

    operations = [
        migrations.RunPython(seed_brand_aliases, noop),
    ]
