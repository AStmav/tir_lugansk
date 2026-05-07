from django.db import migrations


def remove_placeholder_helpful_items(apps, schema_editor):
    HelpfulMenuItem = apps.get_model("pages", "HelpfulMenuItem")
    HelpfulMenuItem.objects.filter(
        title__in=["Новости", "Каталоги", "Статьи"],
        url__in=["/news/", "/catalogs/", "/articles/"],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0011_seed_helpfulmenuitem"),
    ]

    operations = [
        migrations.RunPython(remove_placeholder_helpful_items, migrations.RunPython.noop),
    ]
