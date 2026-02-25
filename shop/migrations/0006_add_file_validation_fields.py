# Generated migration - adds validation fields to ImportFile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_populate_clean_numbers'),
    ]

    operations = [
        migrations.AddField(
            model_name='importfile',
            name='file_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('brands', 'Бренды (ID_brend, NAME)'),
                    ('products', 'Товары (TMP_ID, PROPERTY_P, PROPERTY_T)'),
                    ('analogs', 'OE Аналоги (ID_oe, ID_TOVAR, ID_BREND)'),
                ],
                help_text='Выберите тип импортируемых данных',
                max_length=20,
                null=True,
                verbose_name='Тип файла'
            ),
        ),
        migrations.AddField(
            model_name='importfile',
            name='validation_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Ожидает проверки'),
                    ('valid', 'Структура корректна'),
                    ('invalid', 'Структура не соответствует'),
                    ('warning', 'Есть предупреждения'),
                ],
                default='pending',
                max_length=20,
                verbose_name='Статус валидации'
            ),
        ),
        migrations.AddField(
            model_name='importfile',
            name='validation_message',
            field=models.TextField(
                blank=True,
                help_text='Детали валидации файла',
                verbose_name='Результат проверки'
            ),
        ),
        migrations.AddField(
            model_name='importfile',
            name='detected_fields',
            field=models.JSONField(
                blank=True,
                help_text='Список полей найденных в DBF',
                null=True,
                verbose_name='Обнаруженные поля'
            ),
        ),
        migrations.AddField(
            model_name='importfile',
            name='suggested_type',
            field=models.CharField(
                blank=True,
                help_text='Автоматически определенный тип файла',
                max_length=20,
                verbose_name='Предложенный тип'
            ),
        ),
    ]

