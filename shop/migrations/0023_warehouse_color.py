from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0022_brand_alias'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehouse',
            name='color',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Необязательно. HEX, например #3CC14E — точка рядом с кодом склада на карточке товара.',
                max_length=7,
                verbose_name='Цвет на сайте',
            ),
        ),
    ]
