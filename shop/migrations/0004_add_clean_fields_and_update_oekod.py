# Generated migration - adds clean fields to Product and updates OeKod model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0003_alter_importfile_file'),
    ]

    operations = [
        # Добавляем очищенные поля в Product
        migrations.AddField(
            model_name='product',
            name='catalog_number_clean',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Автоматически генерируется без пробелов и знаков',
                max_length=50,
                verbose_name='Каталожный номер (очищенный)'
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='artikyl_number_clean',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Автоматически генерируется без пробелов и знаков',
                max_length=100,
                verbose_name='Дополнительный номер (очищенный)'
            ),
        ),
        
        # Удаляем старую таблицу OeKod (она пустая)
        migrations.DeleteModel(
            name='OeKod',
        ),
        
        # Создаем новую таблицу OeKod с правильными полями
        migrations.CreateModel(
            name='OeKod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_oe', models.CharField(
                    db_index=True,
                    help_text='Уникальный идентификатор аналога из файла oe_nomer.DBF',
                    max_length=50,
                    unique=True,
                    verbose_name='ID аналога 1С'
                )),
                ('oe_kod', models.CharField(
                    db_index=True,
                    max_length=100,
                    verbose_name='Номер аналога OE'
                )),
                ('oe_kod_clean', models.CharField(
                    blank=True,
                    db_index=True,
                    help_text='Номер без пробелов и знаков препинания для быстрого поиска',
                    max_length=100,
                    verbose_name='Номер аналога OE (очищенный)'
                )),
                ('id_tovar', models.CharField(
                    blank=True,
                    help_text='ID_TOVAR из файла oe_nomer.DBF',
                    max_length=50,
                    verbose_name='ID товара из 1С'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('brand', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='oe_analogs',
                    to='shop.brand',
                    verbose_name='Бренд аналога'
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='oe_analogs',
                    to='shop.product',
                    verbose_name='Товар'
                )),
            ],
            options={
                'verbose_name': 'Аналог OE',
                'verbose_name_plural': 'Аналоги OE',
                'indexes': [
                    models.Index(fields=['oe_kod_clean'], name='shop_oekod_oe_kod__a70d36_idx'),
                    models.Index(fields=['oe_kod'], name='shop_oekod_oe_kod_8bca5e_idx'),
                    models.Index(fields=['id_oe'], name='shop_oekod_id_oe_fef2b0_idx'),
                    models.Index(fields=['id_tovar'], name='shop_oekod_id_tova_c73f9b_idx'),
                ],
            },
        ),
    ]

