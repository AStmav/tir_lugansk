from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0016_add_pg_trgm_and_catalog_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductSlugAlias',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(db_index=True, unique=True, verbose_name='Старый URL')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='slug_aliases', to='shop.product', verbose_name='Товар')),
            ],
            options={
                'verbose_name': 'Алиас URL товара',
                'verbose_name_plural': 'Алиасы URL товаров',
            },
        ),
    ]
