"""
Сборка статических sitemap-файлов для cron.

Пример cron (ежедневно в 04:00 МСК, после импорта 1С):
  0 4 * * * cd /var/www/tir-lugansk && \\
    DJANGO_SETTINGS_MODULE=tir_lugansk.settings_prod \\
    /var/www/tir-lugansk/venv/bin/python manage.py build_sitemaps \\
    >> /var/www/tir-lugansk/logs/build_sitemaps.log 2>&1

Файлы пишутся в SITEMAP_OUTPUT_DIR (по умолчанию <BASE_DIR>/sitemaps/).
Nginx может отдавать их напрямую; иначе Django читает с диска без генерации из БД.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from shop.sitemap_static import build_sitemaps


class Command(BaseCommand):
    help = "Собрать sitemap.xml и дочерние карты в статические файлы"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            type=str,
            default="",
            help="Каталог для XML (по умолчанию SITEMAP_OUTPUT_DIR из settings)",
        )
        parser.add_argument(
            "--domain",
            type=str,
            default="",
            help="Домен для абсолютных URL (по умолчанию SITEMAP_CANONICAL_DOMAIN)",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"]) if options["output_dir"] else None
        domain = options["domain"] or None

        stats = build_sitemaps(output_dir=output_dir, domain=domain)

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: {stats['file_count']} файлов в {stats['output_dir']} "
                f"(домен {stats['domain']}, ~{stats['url_count']} URL)"
            )
        )
        for name in stats["files"]:
            self.stdout.write(f"  - {name}")

        if not getattr(settings, "SITEMAP_STATIC_ENABLED", True):
            self.stdout.write(
                self.style.WARNING(
                    "SITEMAP_STATIC_ENABLED=False — views не читают файлы с диска."
                )
            )
