# Generated manually

from django.db import migrations


def set_quantity_for_in_stock(apps, schema_editor):
    Product = apps.get_model('shop', 'Product')
    Product.objects.filter(in_stock=True, stock_quantity=0).update(stock_quantity=1)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0013_add_stock_quantity'),
    ]

    operations = [
        migrations.RunPython(set_quantity_for_in_stock, noop),
    ]
