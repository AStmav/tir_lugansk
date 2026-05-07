from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0009_headernotice"),
    ]

    operations = [
        migrations.CreateModel(
            name="HelpfulMenuItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=80, verbose_name="Название")),
                (
                    "url",
                    models.CharField(
                        help_text="Внутренний путь (/news/) или полный URL (https://...).",
                        max_length=500,
                        verbose_name="Ссылка",
                    ),
                ),
                ("order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("open_in_new_tab", models.BooleanField(default=False, verbose_name="Открывать в новой вкладке")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
            ],
            options={
                "verbose_name": "Пункт меню «Полезное»",
                "verbose_name_plural": "Пункты меню «Полезное»",
                "ordering": ["order", "title"],
            },
        ),
    ]
