from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0018_warehouse_productoffer'),
        migrations.swappable_dependency('auth.user'),
    ]

    operations = [
        migrations.AddField(
            model_name='warehouse',
            name='import_settings',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Маппинг колонок и строк (header_row, data_start_row, columns, fixed_brand_id).',
                verbose_name='Настройки импорта прайса',
            ),
        ),
        migrations.CreateModel(
            name='WarehousePriceImport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='warehouse_price_imports/', verbose_name='Файл прайса')),
                ('original_filename', models.CharField(blank=True, max_length=255, verbose_name='Имя файла')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Ожидает'),
                        ('processing', 'Обрабатывается'),
                        ('completed', 'Завершён'),
                        ('failed', 'Ошибка'),
                    ],
                    default='pending',
                    max_length=20,
                    verbose_name='Статус',
                )),
                ('total_rows', models.PositiveIntegerField(default=0, verbose_name='Строк прайса')),
                ('updated_rows', models.PositiveIntegerField(default=0, verbose_name='Обновлено предложений')),
                ('skipped_rows', models.PositiveIntegerField(default=0, verbose_name='Пропущено')),
                ('error_count', models.PositiveIntegerField(default=0, verbose_name='Ошибок')),
                ('summary', models.TextField(blank=True, verbose_name='Итог')),
                ('error_log', models.TextField(blank=True, verbose_name='Лог пропусков')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('processed_at', models.DateTimeField(blank=True, null=True, verbose_name='Обработан')),
                ('uploaded_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='auth.user',
                    verbose_name='Загрузил',
                )),
                ('warehouse', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='price_imports',
                    to='shop.warehouse',
                    verbose_name='Склад',
                )),
            ],
            options={
                'verbose_name': 'Импорт прайса склада',
                'verbose_name_plural': 'Импорты прайсов складов',
                'ordering': ['-created_at'],
            },
        ),
    ]
