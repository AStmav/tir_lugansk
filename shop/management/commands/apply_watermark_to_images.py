from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from shop.utils.watermark import apply_watermark_inplace


class Command(BaseCommand):
    help = "Apply watermark to existing images in images/ folder."

    def add_arguments(self, parser):
        parser.add_argument(
            "--section",
            type=str,
            default="",
            help="Process only one section folder inside images/ (for example: 9).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit the number of processed files (0 = no limit).",
        )

    def handle(self, *args, **options):
        images_root = Path(settings.BASE_DIR) / "images"
        if not images_root.exists():
            self.stdout.write(self.style.ERROR(f"Folder not found: {images_root}"))
            return

        section = (options.get("section") or "").strip()
        limit = int(options.get("limit") or 0)

        if section:
            target_root = images_root / section
            if not target_root.exists():
                self.stdout.write(self.style.ERROR(f"Section not found: {target_root}"))
                return
            search_roots = [target_root]
        else:
            search_roots = [images_root]

        exts = {".jpg", ".jpeg", ".png", ".webp"}
        checked = 0
        applied = 0
        skipped = 0

        for root in search_roots:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in exts:
                    continue

                checked += 1
                if apply_watermark_inplace(str(path)):
                    applied += 1
                else:
                    skipped += 1

                if limit and checked >= limit:
                    break
            if limit and checked >= limit:
                break

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Checked: {checked}, watermarked: {applied}, skipped: {skipped}."
            )
        )
