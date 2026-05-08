from django.db import migrations


def seed_useful_categories_posts(apps, schema_editor):
    UsefulCategory = apps.get_model("pages", "UsefulCategory")
    UsefulPost = apps.get_model("pages", "UsefulPost")
    HelpfulMenuItem = apps.get_model("pages", "HelpfulMenuItem")

    categories = [
        {
            "title": "Новости",
            "slug": "news",
            "description": "Обновления ассортимента, графика работы и сервисные объявления.",
            "order": 10,
            "is_active": True,
        },
        {
            "title": "Каталоги",
            "slug": "catalogs",
            "description": "Подборки и справочные материалы для быстрого поиска нужных позиций.",
            "order": 20,
            "is_active": True,
        },
        {
            "title": "Статьи",
            "slug": "articles",
            "description": "Полезные материалы по подбору и эксплуатации запчастей.",
            "order": 30,
            "is_active": True,
        },
    ]

    category_map = {}
    for cat in categories:
        obj, _ = UsefulCategory.objects.update_or_create(slug=cat["slug"], defaults=cat)
        category_map[cat["slug"]] = obj
        HelpfulMenuItem.objects.update_or_create(
            title=cat["title"],
            defaults={
                "url": f"/{cat['slug']}/",
                "order": cat["order"],
                "is_active": True,
                "open_in_new_tab": False,
            },
        )

    posts = [
        {
            "category_slug": "news",
            "title": "Обновление ассортимента",
            "summary": "Еженедельное поступление запчастей по основным маркам европейских грузовиков.",
            "content": "",
            "order": 10,
            "is_active": True,
        },
        {
            "category_slug": "catalogs",
            "title": "Каталог тормозной системы",
            "summary": "Позиции по колодкам, дискам, барабанам и комплектам обслуживания.",
            "content": "",
            "order": 10,
            "is_active": True,
        },
        {
            "category_slug": "articles",
            "title": "Как подобрать аналог детали правильно",
            "summary": "Ключевые шаги проверки OEM-номера и совместимости перед покупкой.",
            "content": "",
            "order": 10,
            "is_active": True,
        },
    ]

    for post in posts:
        category = category_map.get(post["category_slug"])
        if not category:
            continue
        UsefulPost.objects.update_or_create(
            category=category,
            title=post["title"],
            defaults={
                "summary": post["summary"],
                "content": post["content"],
                "order": post["order"],
                "is_active": post["is_active"],
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0015_usefulcategory_usefulpost"),
    ]

    operations = [
        migrations.RunPython(seed_useful_categories_posts, migrations.RunPython.noop),
    ]
