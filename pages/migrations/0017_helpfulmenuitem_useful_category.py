from django.db import migrations, models
import django.db.models.deletion


def link_menu_items_to_categories(apps, schema_editor):
    HelpfulMenuItem = apps.get_model("pages", "HelpfulMenuItem")
    UsefulCategory = apps.get_model("pages", "UsefulCategory")

    by_slug = {c.slug: c for c in UsefulCategory.objects.all()}

    for item in HelpfulMenuItem.objects.all():
        if item.useful_category_id:
            continue
        raw_url = (item.url or "").strip().strip("/")
        slug = raw_url.split("/")[-1] if raw_url else ""
        category = by_slug.get(slug)
        if not category:
            continue
        item.useful_category = category
        item.save(update_fields=["useful_category"])


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0016_seed_useful_categories_posts"),
    ]

    operations = [
        migrations.AddField(
            model_name="helpfulmenuitem",
            name="useful_category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="menu_items",
                to="pages.usefulcategory",
                verbose_name="Категория полезного",
            ),
        ),
        migrations.RunPython(link_menu_items_to_categories, migrations.RunPython.noop),
    ]
