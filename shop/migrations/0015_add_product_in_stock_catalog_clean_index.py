# Generated manually — составной индекс для каталога/поиска (п. 4.1 роадмапа)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0014_populate_stock_quantity'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='product',
            index=models.Index(
                fields=['in_stock', 'catalog_number_clean'],
                name='shop_prod_stock_cat_idx',
            ),
        ),
    ]
