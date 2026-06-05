from django.db import migrations, models


def enable_short_urls_for_legacy_categories(apps, schema_editor):
    UsefulCategory = apps.get_model("pages", "UsefulCategory")
    UsefulCategory.objects.filter(slug__in=["news", "catalogs", "articles"]).update(use_short_url=True)


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0018_priceinquiry_consent_personal_data_page"),
    ]

    operations = [
        migrations.AddField(
            model_name="usefulcategory",
            name="posts_per_page",
            field=models.PositiveIntegerField(
                default=12,
                help_text="Сколько записей показывать в списке до пагинации.",
                verbose_name="Материалов на странице",
            ),
        ),
        migrations.AddField(
            model_name="usefulcategory",
            name="use_short_url",
            field=models.BooleanField(
                default=False,
                help_text="Категория открывается по адресу /slug/ вместо /useful/slug/ (как /news/).",
                verbose_name="Короткий URL",
            ),
        ),
        migrations.RunPython(
            enable_short_urls_for_legacy_categories,
            migrations.RunPython.noop,
        ),
    ]
