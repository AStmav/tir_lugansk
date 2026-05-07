from django.db import migrations


def seed_real_helpful_items(apps, schema_editor):
    HelpfulMenuItem = apps.get_model("pages", "HelpfulMenuItem")

    items = [
        {"title": "Новости", "url": "/news/", "order": 10, "is_active": True, "open_in_new_tab": False},
        {"title": "Каталоги", "url": "/catalogs/", "order": 20, "is_active": True, "open_in_new_tab": False},
        {"title": "Статьи", "url": "/articles/", "order": 30, "is_active": True, "open_in_new_tab": False},
    ]

    for item in items:
        HelpfulMenuItem.objects.update_or_create(title=item["title"], defaults=item)


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0012_remove_placeholder_helpful_items"),
    ]

    operations = [
        migrations.RunPython(seed_real_helpful_items, migrations.RunPython.noop),
    ]
