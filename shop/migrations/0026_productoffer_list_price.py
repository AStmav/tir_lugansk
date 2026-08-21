from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0025_warehousepriceimport_progress'),
    ]

    operations = [
        migrations.AddField(
            model_name='productoffer',
            name='list_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Цена из файла поставщика до наценки склада (заполняется при импорте прайса).',
                max_digits=10,
                null=True,
                verbose_name='Цена прайса',
            ),
        ),
    ]
