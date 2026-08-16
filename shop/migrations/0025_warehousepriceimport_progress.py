from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0024_category_section_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehousepriceimport',
            name='import_settings',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Маппинг колонок для этого импорта (header_row, data_start_row, columns).',
                verbose_name='Настройки импорта',
            ),
        ),
        migrations.AddField(
            model_name='warehousepriceimport',
            name='processed_rows',
            field=models.PositiveIntegerField(default=0, verbose_name='Обработано строк'),
        ),
        migrations.AddField(
            model_name='warehousepriceimport',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Начат'),
        ),
    ]
