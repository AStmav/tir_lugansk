from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def create_default_warehouse(apps, schema_editor):
    Warehouse = apps.get_model('shop', 'Warehouse')
    if Warehouse.objects.filter(is_default=True).exists():
        return
    Warehouse.objects.create(
        name_internal='Основной',
        name_public='Склад',
        delivery_days=0,
        last_uploaded_at=timezone.now(),
        is_active=True,
        is_default=True,
        sort_order=0,
    )


def noop_reverse(apps, schema_editor):
    Warehouse = apps.get_model('shop', 'Warehouse')
    Warehouse.objects.filter(is_default=True, name_internal='Основной').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0017_productslugalias'),
    ]

    operations = [
        migrations.CreateModel(
            name='Warehouse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name_internal', models.CharField(
                    help_text='Внутреннее название для оператора, например: Мотор-Доктор1',
                    max_length=120,
                    verbose_name='Название склада',
                )),
                ('name_public', models.CharField(
                    help_text='Что видит покупатель, например: VS_002',
                    max_length=64,
                    verbose_name='Название на сайте',
                )),
                ('delivery_days', models.PositiveSmallIntegerField(
                    default=0,
                    help_text='0 = сегодня / на складе. Можно переопределить в предложении.',
                    verbose_name='Срок доставки (дней)',
                )),
                ('last_uploaded_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата последней загрузки')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('is_default', models.BooleanField(
                    default=False,
                    help_text='Используется как фолбэк для товаров без строк предложений.',
                    verbose_name='Основной склад',
                )),
                ('sort_order', models.PositiveIntegerField(default=100, verbose_name='Порядок сортировки')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлён')),
            ],
            options={
                'verbose_name': 'Склад',
                'verbose_name_plural': 'Склады',
                'ordering': ['sort_order', 'name_internal'],
            },
        ),
        migrations.CreateModel(
            name='ProductOffer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Цена')),
                ('old_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Старая цена')),
                ('stock_quantity', models.PositiveIntegerField(default=0, verbose_name='Остаток')),
                ('delivery_days', models.PositiveSmallIntegerField(
                    blank=True,
                    help_text='Пусто — берётся срок склада.',
                    null=True,
                    verbose_name='Срок доставки (дней)',
                )),
                ('is_active', models.BooleanField(default=True, verbose_name='Активно')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='offers',
                    to='shop.product',
                    verbose_name='Товар',
                )),
                ('warehouse', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='offers',
                    to='shop.warehouse',
                    verbose_name='Склад',
                )),
            ],
            options={
                'verbose_name': 'Предложение',
                'verbose_name_plural': 'Предложения',
                'ordering': ['warehouse__sort_order', 'price'],
            },
        ),
        migrations.AddIndex(
            model_name='productoffer',
            index=models.Index(fields=['product', 'is_active'], name='shop_offer_prod_active_idx'),
        ),
        migrations.AddIndex(
            model_name='productoffer',
            index=models.Index(fields=['warehouse', 'is_active'], name='shop_offer_wh_active_idx'),
        ),
        migrations.AddConstraint(
            model_name='productoffer',
            constraint=models.UniqueConstraint(
                fields=('product', 'warehouse'),
                name='shop_productoffer_product_warehouse_uniq',
            ),
        ),
        migrations.RunPython(create_default_warehouse, noop_reverse),
    ]
