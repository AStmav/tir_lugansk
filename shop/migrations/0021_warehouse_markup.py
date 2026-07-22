from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0020_brand_article_prefix'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehouse',
            name='markup_mode',
            field=models.CharField(
                choices=[
                    ('none', 'Без наценки'),
                    ('percent', 'Один процент'),
                    ('ranges', 'По диапазонам цены'),
                ],
                default='none',
                help_text='Наценка применяется к цене из файла прайса при загрузке.',
                max_length=20,
                verbose_name='Режим наценки',
            ),
        ),
        migrations.AddField(
            model_name='warehouse',
            name='markup_percent',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0'),
                help_text='Для режима «Один процент». Пример: 23 = +23% к цене прайса.',
                max_digits=6,
                verbose_name='Процент наценки',
            ),
        ),
        migrations.CreateModel(
            name='WarehouseMarkupRange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('price_from', models.DecimalField(
                    decimal_places=2,
                    help_text='Включительно',
                    max_digits=12,
                    verbose_name='Цена от',
                )),
                ('price_to', models.DecimalField(
                    blank=True,
                    decimal_places=2,
                    help_text='Включительно. Пусто = без верхней границы.',
                    max_digits=12,
                    null=True,
                    verbose_name='Цена до',
                )),
                ('percent', models.DecimalField(
                    decimal_places=2,
                    max_digits=6,
                    verbose_name='Наценка %',
                )),
                ('warehouse', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='markup_ranges',
                    to='shop.warehouse',
                    verbose_name='Склад',
                )),
            ],
            options={
                'verbose_name': 'Диапазон наценки',
                'verbose_name_plural': 'Диапазоны наценки',
                'ordering': ['price_from', 'id'],
            },
        ),
    ]
