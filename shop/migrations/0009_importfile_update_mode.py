# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0008_add_seo_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='importfile',
            name='update_mode',
            field=models.CharField(
                choices=[
                    ('update', '🔄 Обновить существующие'),
                    ('skip', '⏭️ Пропустить существующие'),
                    ('create_only', '🔸 Создать дубликаты (старый режим)'),
                ],
                default='update',
                help_text='Что делать при повторном импорте существующих товаров?',
                max_length=20,
                verbose_name='Режим обработки дубликатов'
            ),
        ),
    ]

