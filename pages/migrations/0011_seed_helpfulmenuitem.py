from django.db import migrations


def seed_helpful_menu_items(apps, schema_editor):
    HelpfulMenuItem = apps.get_model("pages", "HelpfulMenuItem")

    # Осознанно не добавляем тестовые ссылки-заглушки на несуществующие разделы.
    items = []

    for item in items:
        HelpfulMenuItem.objects.update_or_create(
            title=item["title"],
            defaults=item,
        )


def unseed_helpful_menu_items(apps, schema_editor):
    HelpfulMenuItem = apps.get_model("pages", "HelpfulMenuItem")
    HelpfulMenuItem.objects.filter(title__in=["Новости", "Каталоги", "Статьи"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0010_helpfulmenuitem"),
    ]

    operations = [
        migrations.RunPython(seed_helpful_menu_items, unseed_helpful_menu_items),
    ]
