"""
Импорт изображений из входящей папки с той же структурой, что и images: {section_id}/{filename}.
Копирование в images/{section_id}/ с проверками: не перезаписывать существующие (дубликаты), пропускать битые файлы.
"""
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


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
        return True
    except Exception:
        return False


def process_bulk_image_items(items, remove_source_if_path=False):
    """
    Копирует изображения в images/{section_id}/{filename}, сохраняя структуру. Привязывает к товарам по tmp_id.

    items: список кортежей (section_id, filename, source_path).
      section_id — имя подпапки во входящей (как в images);
      filename — имя файла (tmp_id.jpg, tmp_id_1.jpg и т.д.);
      source_path — полный путь к файлу на диске.
    remove_source_if_path: после успешного копирования удалить исходный файл.

    Проверки: не перезаписывать существующий файл в images/{section_id}/; пропускать битые файлы (PIL).

    Возвращает: (linked_count, not_found_list, errors_count, skipped_duplicates_count, invalid_files_count, restored_count).
    restored_count — файл скопирован на диск, запись ProductImage уже была (файл восстановлен).
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

        # Не перезаписывать существующий файл и папку (дубликат)
        section_dir = images_base / section_id
        dest_path = section_dir / filename
        rel_path = f"images/{section_id}/{filename}"
        if dest_path.exists():
            skipped_duplicates += 1
            if ProductImage.objects.filter(product=product, image=rel_path).exists():
                if remove_source_if_path:
                    try:
                        os.remove(source_path)
                    except OSError:
                        pass
            continue

        try:
            section_dir.mkdir(parents=True, exist_ok=True)
            with open(source_path, 'rb') as fh:
                content = fh.read()
            dest_path.write_bytes(content)

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
        except Exception as e:
            errors += 1
            logger.exception("Ошибка обработки %s: %s", rel_path, e)

    return linked_count, not_found, errors, skipped_duplicates, invalid_files, restored_count
