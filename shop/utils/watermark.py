from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import shutil
import tempfile

from django.conf import settings

# Чтобы nginx (www-data) читал файлы после импорта/водяного знака без ручного find/chmod.
_FILE_MODE = 0o644
_DIR_MODE = 0o755


def _ensure_web_readable_image_path(destination_path: str) -> None:
    path = Path(destination_path).resolve()
    images_root = (Path(settings.BASE_DIR) / "images").resolve()
    try:
        if path.is_file():
            path.chmod(_FILE_MODE)
        parent = path.parent
        for _ in range(32):
            if not parent.is_dir():
                break
            try:
                parent.chmod(_DIR_MODE)
            except OSError:
                pass
            if parent == images_root:
                break
            if parent.parent == parent:
                break
            parent = parent.parent
    except OSError:
        pass


def _env_flag(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def _watermark_path() -> Path | None:
    raw = getattr(settings, "WATERMARK_IMAGE_PATH", "")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(settings.BASE_DIR) / path
    return path if path.exists() and path.is_file() else None


def _copy_without_watermark(source_path: str, destination_path: str) -> None:
    Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)
    _ensure_web_readable_image_path(destination_path)


def save_with_optional_watermark(source_path: str, destination_path: str) -> bool:
    """
    Saves image to destination with optional watermark.

    Returns True if watermark was applied, False if plain copy.
    """
    if not _env_flag(getattr(settings, "WATERMARK_ENABLED", False)):
        _copy_without_watermark(source_path, destination_path)
        return False

    watermark_path = _watermark_path()
    if watermark_path is None:
        _copy_without_watermark(source_path, destination_path)
        return False

    ext = Path(destination_path).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        _copy_without_watermark(source_path, destination_path)
        return False

    try:
        from PIL import Image
    except Exception:
        _copy_without_watermark(source_path, destination_path)
        return False

    with Image.open(source_path) as base_img:
        base = base_img.convert("RGBA")
        with Image.open(watermark_path) as wm_img:
            watermark = wm_img.convert("RGBA")

        scale = float(getattr(settings, "WATERMARK_SCALE", 0.22))
        opacity = float(getattr(settings, "WATERMARK_OPACITY", 0.18))
        margin = int(getattr(settings, "WATERMARK_MARGIN", 16))
        fit_mode = str(getattr(settings, "WATERMARK_FIT_MODE", "full")).strip().lower()

        if fit_mode == "full":
            # Full-size overlay mode: watermark covers the whole image area.
            wm_resized = watermark.resize((base.width, base.height))
            x = 0
            y = 0
        else:
            target_w = max(1, int(base.width * scale))
            ratio = target_w / max(1, watermark.width)
            target_h = max(1, int(watermark.height * ratio))
            wm_resized = watermark.resize((target_w, target_h))

        if opacity < 1:
            alpha = wm_resized.getchannel("A")
            alpha = alpha.point(lambda x: int(x * max(0.0, min(1.0, opacity))))
            wm_resized.putalpha(alpha)

        if fit_mode != "full":
            position = str(getattr(settings, "WATERMARK_POSITION", "center")).strip().lower()
            if position == "bottom_right":
                x = max(0, base.width - wm_resized.width - margin)
                y = max(0, base.height - wm_resized.height - margin)
            elif position == "top_left":
                x = max(0, margin)
                y = max(0, margin)
            elif position == "top_right":
                x = max(0, base.width - wm_resized.width - margin)
                y = max(0, margin)
            elif position == "bottom_left":
                x = max(0, margin)
                y = max(0, base.height - wm_resized.height - margin)
            else:
                # Default: center
                x = max(0, (base.width - wm_resized.width) // 2)
                y = max(0, (base.height - wm_resized.height) // 2)
        base.alpha_composite(wm_resized, (x, y))

        destination = Path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if ext in {".jpg", ".jpeg"}:
            base.convert("RGB").save(destination, quality=90, optimize=True)
        else:
            base.save(destination, optimize=True)

    _ensure_web_readable_image_path(str(destination_path))
    return True


def apply_watermark_inplace(image_path: str) -> bool:
    """
    Applies watermark to an existing image file in place.

    Returns True if watermark was applied, False otherwise.
    """
    src = Path(image_path)
    if not src.exists() or not src.is_file():
        return False

    with tempfile.NamedTemporaryFile(
        suffix=src.suffix,
        prefix="wm_",
        delete=False,
        dir=str(src.parent),
    ) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        applied = save_with_optional_watermark(str(src), str(temp_path))
        if not applied:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            return False

        shutil.move(str(temp_path), str(src))
        return True
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False
