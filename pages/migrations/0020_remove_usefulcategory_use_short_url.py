from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0019_usefulcategory_pagination_short_url"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="usefulcategory",
            name="use_short_url",
        ),
    ]
