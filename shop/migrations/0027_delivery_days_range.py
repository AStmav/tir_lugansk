from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0026_productoffer_list_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehouse',
            name='delivery_days_to',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Необязательно. Если больше «от» — на сайте «4 - 6 дней».',
                null=True,
                verbose_name='Срок доставки до (дней)',
            ),
        ),
        migrations.AddField(
            model_name='productoffer',
            name='delivery_days_to',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Пусто — берётся верхняя граница со склада.',
                null=True,
                verbose_name='Срок доставки до (дней)',
            ),
        ),
        migrations.AlterField(
            model_name='productoffer',
            name='delivery_days',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Пусто — берётся срок склада.',
                null=True,
                verbose_name='Срок доставки от (дней)',
            ),
        ),
        migrations.AlterField(
            model_name='warehouse',
            name='delivery_days',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text='0 = сегодня / на складе. Можно переопределить в предложении.',
                verbose_name='Срок доставки от (дней)',
            ),
        ),
    ]
