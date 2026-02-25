# Generated manually - Remove unique constraint from id_oe and add composite unique index

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0010_oekod_product_nullable'),
    ]

    operations = [
        # Убираем unique=True с id_oe
        migrations.AlterField(
            model_name='oekod',
            name='id_oe',
            field=models.CharField(
                db_index=True,
                help_text='Идентификатор аналога из файла oe_nomer.DBF. Один id_oe может быть связан с разными товарами (разные ID_TOVAR).',
                max_length=50,
                verbose_name='ID аналога 1С'
            ),
        ),
        # Добавляем db_index к id_tovar (если его еще нет)
        migrations.AlterField(
            model_name='oekod',
            name='id_tovar',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='ID_TOVAR из файла oe_nomer.DBF. Используется для связи с товаром и составного уникального индекса.',
                max_length=50,
                verbose_name='ID товара из 1С'
            ),
        ),
        # Добавляем составной уникальный индекс
        migrations.AlterUniqueTogether(
            name='oekod',
            unique_together={('id_oe', 'id_tovar')},
        ),
    ]

