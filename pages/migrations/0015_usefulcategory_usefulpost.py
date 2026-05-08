from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0014_seed_useful_pages"),
    ]

    operations = [
        migrations.CreateModel(
            name="UsefulCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120, verbose_name="Название категории")),
                ("slug", models.SlugField(unique=True, verbose_name="Slug")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
            ],
            options={
                "verbose_name": "Категория раздела «Полезное»",
                "verbose_name_plural": "Категории раздела «Полезное»",
                "ordering": ["order", "title"],
            },
        ),
        migrations.CreateModel(
            name="UsefulPost",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180, verbose_name="Заголовок")),
                ("summary", models.TextField(blank=True, verbose_name="Краткое описание")),
                ("content", models.TextField(blank=True, verbose_name="Содержимое")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("published_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="Дата публикации")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="posts",
                        to="pages.usefulcategory",
                        verbose_name="Категория",
                    ),
                ),
            ],
            options={
                "verbose_name": "Материал раздела «Полезное»",
                "verbose_name_plural": "Материалы раздела «Полезное»",
                "ordering": ["-published_at", "order", "title"],
            },
        ),
    ]
