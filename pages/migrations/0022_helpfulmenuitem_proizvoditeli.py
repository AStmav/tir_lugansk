from django.db import migrations


def seed_proizvoditeli_menu_item(apps, schema_editor):
    HelpfulMenuItem = apps.get_model("pages", "HelpfulMenuItem")
    HelpfulMenuItem.objects.update_or_create(
        title="Производители",
        defaults={
            "url": "/shop/brands/",
            "order": 25,
            "is_active": True,
            "open_in_new_tab": False,
        },
    )


def remove_proizvoditeli_menu_item(apps, schema_editor):
    HelpfulMenuItem = apps.get_model("pages", "HelpfulMenuItem")
    HelpfulMenuItem.objects.filter(title="Производители", url="/shop/brands/").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0021_usefulpost_attachment"),
    ]

    operations = [
        migrations.RunPython(seed_proizvoditeli_menu_item, remove_proizvoditeli_menu_item),
    ]
