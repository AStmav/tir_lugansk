# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0009_importfile_update_mode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='oekod',
            name='product',
            field=models.ForeignKey(
                blank=True,
                help_text='Товар-владелец аналога. Может быть NULL если товар ещё не импортирован.',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='oe_analogs',
                to='shop.product',
                verbose_name='Товар'
            ),
        ),
    ]

