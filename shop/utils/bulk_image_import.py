"""
Импорт изображений из входящей папки с той же структурой, что и images: {section_id}/{filename}.
Копирование в images/{section_id}/ с проверками: не перезаписывать существующие (дубликаты), пропускать битые файлы.
"""
import os
import logging
from pathlib import Path
from typing import List, Optional, Set, Tuple

from django.conf import settings
from shop.utils.watermark import save_with_optional_watermark

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
IncomingItem = Tuple[str, str, str]


def _extract_tmp_id_and_ext(filename):
    """Из имени файла извлекает tmp_id и расширение. Поддерживает tmp_id_1.jpg."""
    ext = os.path.splitext(filename)[1].lower()
    base = os.path.splitext(filename)[0]
    tmp_id = base.rsplit('_', 1)[0] if '_' in base else base
    return tmp_id, ext


def _is_valid_image(file_path):
    """Проверяет, что файл не битый (открывается как изображение)."""
    try:
        from PIL import Image
        if os.path.getsize(file_path) == 0:
            return False
        with Image.open(file_path) as img:
            img.verify()
        # verify() не декодирует полностью; обрезанные JPEG часто падают только на load().
        with Image.open(file_path) as img:
            img.load()
        return True
    except Exception:
        return False


def get_incoming_images_dir() -> Path:
    incoming_dir = getattr(settings, 'INCOMING_IMAGES_DIR', None) or (settings.BASE_DIR / 'incoming_images')
    return Path(incoming_dir)


def find_product_by_key(product_key: str):
    """Поиск товара по code, tmp_id или catalog_number."""
    from django.db.models import Q
    from shop.models import Product

    key = (product_key or '').strip()
    if not key:
        return None
    return Product.objects.filter(
        Q(code=key) | Q(tmp_id=key) | Q(catalog_number=key)
    ).first()


def product_match_keys(product) -> Set[str]:
    keys: Set[str] = set()
    for value in (product.tmp_id, product.code, product.catalog_number):
        if value:
            keys.add(str(value).strip())
    return keys


def collect_incoming_image_items(
    incoming_dir: Optional[Path] = None,
    *,
    product_key: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[IncomingItem]:
    """Сканирует incoming_images и возвращает (section_id, filename, absolute_path)."""
    incoming_path = Path(incoming_dir or get_incoming_images_dir())
    allowed_keys: Optional[Set[str]] = None
    if product_key:
        product = find_product_by_key(product_key)
        if product is None:
            raise LookupError(f'Товар не найден: {product_key}')
        allowed_keys = product_match_keys(product)

    items: List[IncomingItem] = []
    seen_realpaths: Set[str] = set()
    incoming_str = str(incoming_path)
    if not incoming_path.is_dir():
        return items

    for root, _dirs, files in os.walk(incoming_str):
        rel = os.path.relpath(root, incoming_str)
        section_id = '_imported' if rel == '.' else rel.replace('\\', '/')
        for filename in files:
            _, ext = _extract_tmp_id_and_ext(filename)
            if ext not in IMAGE_EXTENSIONS:
                continue
            tmp_id, _ = _extract_tmp_id_and_ext(filename)
            if allowed_keys is not None and tmp_id not in allowed_keys:
                continue
            path = os.path.join(root, filename)
            if not os.path.isfile(path):
                continue
            try:
                key = os.path.realpath(path)
            except OSError:
                key = os.path.abspath(path)
            if key in seen_realpaths:
                continue
            seen_realpaths.add(key)
            items.append((section_id, filename, path))
            if limit and len(items) >= limit:
                return items
    return items


def count_image_files(base_dir: Path) -> int:
    if not base_dir.is_dir():
        return 0
    total = 0
    for _root, _dirs, files in os.walk(base_dir):
        for filename in files:
            _, ext = os.path.splitext(filename)
            if ext.lower() in IMAGE_EXTENSIONS:
                total += 1
    return total


def find_files_by_basename(base_dir: Path, basename: str) -> List[str]:
    """Ищет файлы, имя которых начинается с basename (например 000206631)."""
    if not base_dir.is_dir():
        return []
    matches: List[str] = []
    for root, _dirs, files in os.walk(base_dir):
        for filename in files:
            if filename == basename or filename.startswith(f'{basename}_') or filename.startswith(f'{basename}.'):
                matches.append(str(Path(root) / filename))
    return sorted(matches)


def process_bulk_image_items(items, remove_source_if_path=False, overwrite_existing=False):
    """
    Копирует изображения в images/{section_id}/{filename}, сохраняя структуру. Привязывает к товарам по tmp_id.

    items: список кортежей (section_id, filename, source_path).
    remove_source_if_path: после успешного копирования удалить исходный файл.
    overwrite_existing: если True — перезаписывать файл в images/, если он уже есть.

    Возвращает: (linked_count, not_found_list, errors_count, skipped_duplicates_count, invalid_files_count, restored_count).
    """
    from shop.models import Product, ProductImage

    images_base = settings.BASE_DIR / 'images'
    try:
        images_base.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.exception("Не удалось создать images/: %s", e)
        return 0, [], 0, 0, 0, 0

    products_by_tmp_id = {}
    products_by_code = {}
    for p in Product.objects.only('id', 'tmp_id', 'code').iterator(chunk_size=5000):
        if p.tmp_id:
            products_by_tmp_id[p.tmp_id] = p
        if p.code:
            products_by_code[p.code.strip()] = p

    linked_count = 0
    not_found = []
    errors = 0
    skipped_duplicates = 0
    invalid_files = 0
    restored_count = 0  # файл скопирован, запись в БД уже была — не удаляем файл
    product_order = {}

    for section_id, filename, source_path in items:
        if not isinstance(source_path, str) or not os.path.isfile(source_path):
            errors += 1
            continue

        tmp_id, ext = _extract_tmp_id_and_ext(filename)
        if ext not in IMAGE_EXTENSIONS:
            continue

        # Битый файл — пропускаем
        if not _is_valid_image(source_path):
            invalid_files += 1
            logger.warning("Битый или пустой файл, пропуск: %s", source_path)
            continue

        product = products_by_tmp_id.get(tmp_id) or products_by_code.get(tmp_id)
        if not product:
            not_found.append(f"{section_id}/{filename}")
            continue

        section_dir = images_base / section_id
        dest_path = section_dir / filename
        rel_path = f"images/{section_id}/{filename}"
        if dest_path.exists() and not overwrite_existing:
            skipped_duplicates += 1
            if ProductImage.objects.filter(product=product, image=rel_path).exists():
                if remove_source_if_path:
                    try:
                        os.remove(source_path)
                    except OSError:
                        pass
            continue

        # Параллельный второй импорт (другой воркер / двойной POST) уже мог удалить исходник.
        if not os.path.isfile(source_path):
            errors += 1
            logger.warning(
                "Исходник отсутствует при копировании (часто — параллельный импорт): %s → %s",
                source_path,
                rel_path,
            )
            continue

        try:
            section_dir.mkdir(parents=True, exist_ok=True)
            save_with_optional_watermark(str(source_path), str(dest_path))

            if product.id not in product_order:
                product_order[product.id] = ProductImage.objects.filter(product=product).count()
            order = product_order[product.id]
            is_main = order == 0

            if ProductImage.objects.filter(product=product, image=rel_path).exists():
                product_order[product.id] += 1
                # Запись в БД уже есть — файл только что скопирован, не удаляем его (восстановление файла на диске)
                restored_count += 1
                if remove_source_if_path:
                    try:
                        os.remove(source_path)
                    except OSError:
                        pass
                continue

            ProductImage.objects.create(
                product=product,
                image=rel_path,
                is_main=is_main,
                order=order,
            )
            product_order[product.id] = order + 1
            linked_count += 1

            if remove_source_if_path:
                try:
                    os.remove(source_path)
                except OSError:
                    pass
        except FileNotFoundError as e:
            errors += 1
            logger.warning(
                "Файл исчез во время обработки %s (параллельный импорт?): %s",
                rel_path,
                e,
            )
        except Exception as e:
            errors += 1
            logger.exception("Ошибка обработки %s: %s", rel_path, e)

    return linked_count, not_found, errors, skipped_duplicates, invalid_files, restored_count
