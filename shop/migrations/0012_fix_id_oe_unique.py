# Generated manually - Fix id_oe to be unique (it's a unique identifier)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0011_remove_unique_id_oe_add_composite_index'),
    ]

    operations = [
        # Возвращаем unique=True для id_oe (это уникальный идентификатор)
        migrations.AlterField(
            model_name='oekod',
            name='id_oe',
            field=models.CharField(
                db_index=True,
                help_text='Уникальный порядковый номер аналога из файла oe_nomer.DBF. Каждый аналог имеет уникальный ID_OE.',
                max_length=50,
                unique=True,
                verbose_name='ID аналога 1С'
            ),
        ),
        # Убираем unique_together (не нужен, т.к. id_oe уже уникален)
        migrations.AlterUniqueTogether(
            name='oekod',
            unique_together=set(),
        ),
    ]

