from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0007_maxnotificationrecipient'),
    ]

    operations = [
        migrations.AddField(
            model_name='priceinquiry',
            name='comment',
            field=models.TextField(blank=True, verbose_name='Комментарий'),
        ),
    ]

