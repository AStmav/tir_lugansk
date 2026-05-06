from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0008_priceinquiry_comment"),
    ]

    operations = [
        migrations.CreateModel(
            name="HeaderNotice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, max_length=120, verbose_name="Заголовок")),
                ("message", models.CharField(max_length=280, verbose_name="Текст сообщения")),
                ("link_url", models.URLField(blank=True, verbose_name="Ссылка")),
                ("link_text", models.CharField(blank=True, max_length=60, verbose_name="Текст ссылки")),
                (
                    "level",
                    models.CharField(
                        choices=[("info", "Информация"), ("warning", "Предупреждение"), ("critical", "Критично")],
                        default="info",
                        max_length=16,
                        verbose_name="Уровень важности",
                    ),
                ),
                ("is_active", models.BooleanField(default=False, verbose_name="Включено")),
                ("starts_at", models.DateTimeField(blank=True, null=True, verbose_name="Показывать с")),
                ("ends_at", models.DateTimeField(blank=True, null=True, verbose_name="Показывать до")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
            ],
            options={
                "verbose_name": "Важное сообщение в шапке",
                "verbose_name_plural": "Важные сообщения в шапке",
                "ordering": ["-is_active", "-updated_at"],
            },
        ),
    ]
