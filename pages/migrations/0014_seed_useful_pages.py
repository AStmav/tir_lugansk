from django.db import migrations


def seed_useful_pages(apps, schema_editor):
    Page = apps.get_model("pages", "Page")

    pages = [
        {
            "slug": "news",
            "title": "Новости",
            "page_type": "custom",
            "meta_description": "Обновления ассортимента, графика работы и сервисные объявления.",
            "content": """
<div class="reviews__list" style="margin-top: 26px; flex-wrap: wrap; justify-content: flex-start;">
  <article class="reviews__item" style="background: #fff; border: 1px solid #e9ecef; border-radius: 14px; padding: 20px; text-align: left; max-width: 360px;">
    <h3 style="margin: 0 0 10px;">Обновление ассортимента</h3>
    <p style="margin: 0 0 10px; color: #4b5563;">Еженедельное поступление запчастей по основным маркам европейских грузовиков.</p>
    <p style="margin: 0; font-size: 13px; color: #6b7280;">Май 2026</p>
  </article>
</div>
""".strip(),
            "is_active": True,
        },
        {
            "slug": "catalogs",
            "title": "Каталоги",
            "page_type": "custom",
            "meta_description": "Подборки и справочные материалы для быстрого поиска нужных позиций.",
            "content": """
<div class="reviews__list" style="margin-top: 26px; flex-wrap: wrap; justify-content: flex-start;">
  <article class="reviews__item" style="background: #fff; border: 1px solid #e9ecef; border-radius: 14px; padding: 20px; text-align: left; max-width: 360px;">
    <h3 style="margin: 0 0 10px;">Каталог тормозной системы</h3>
    <p style="margin: 0 0 10px; color: #4b5563;">Позиции по колодкам, дискам, барабанам и комплектам обслуживания.</p>
    <p style="margin: 0; font-size: 13px; color: #6b7280;">PDF / онлайн-версия</p>
  </article>
</div>
""".strip(),
            "is_active": True,
        },
        {
            "slug": "articles",
            "title": "Статьи",
            "page_type": "custom",
            "meta_description": "Полезные материалы по подбору и эксплуатации запчастей.",
            "content": """
<div class="reviews__list" style="margin-top: 26px; flex-wrap: wrap; justify-content: flex-start;">
  <article class="reviews__item" style="background: #fff; border: 1px solid #e9ecef; border-radius: 14px; padding: 20px; text-align: left; max-width: 360px;">
    <h3 style="margin: 0 0 10px;">Как подобрать аналог детали правильно</h3>
    <p style="margin: 0 0 10px; color: #4b5563;">Ключевые шаги проверки OEM-номера и совместимости перед покупкой.</p>
    <p style="margin: 0; font-size: 13px; color: #6b7280;">Руководство</p>
  </article>
</div>
""".strip(),
            "is_active": True,
        },
    ]

    for page in pages:
        Page.objects.update_or_create(slug=page["slug"], defaults=page)


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0013_seed_real_helpful_items"),
    ]

    operations = [
        migrations.RunPython(seed_useful_pages, migrations.RunPython.noop),
    ]
