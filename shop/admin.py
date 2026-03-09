from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.urls import path
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404, render
from django.contrib import messages
from django.core.management import call_command
from django.conf import settings
import os
import threading
import traceback
import logging
from .models import Category, SubCategory, Brand, Product, ProductImage, ProductAnalog, OeKod, ImportFile
from .audit_log import log_audit

# Глобальный logger для всего модуля
logger = logging.getLogger(__name__)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductAnalogInline(admin.TabularInline):
    model = ProductAnalog
    fk_name = 'product'
    extra = 1
    verbose_name = 'Аналог'
    verbose_name_plural = 'Аналоги'


class OeKodInline(admin.TabularInline):
    model = OeKod
    extra = 1
    verbose_name = 'Аналог OE'
    verbose_name_plural = 'Аналоги OE'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['tree_name', 'edit_button', 'parent', 'is_active', 'order']
    list_filter = ['parent', 'is_active']
    search_fields = ['name']
    list_editable = ['is_active', 'order']
    ordering = ['order', 'name']
    
    def tree_name(self, obj):
        """Отображение названия с отступами для древовидной структуры"""
        try:
            level = 0 if not obj.parent else 1  # Упрощенно: 0 или 1
            indent = "—" * level * 2
            return format_html(
                '<span style="margin-left: {}px;">{} {}</span>',
                level * 20,
                indent,
                obj.name
            )
        except:
            return obj.name
    tree_name.short_description = 'Название'
    
    def edit_button(self, obj):
        """Кнопка редактирования с карандашиком"""
        return format_html(
            '<button type="button" class="btn-edit-category" data-id="{}" data-name="{}" data-parent="{}" '
            'style="background: none; border: none; cursor: pointer; font-size: 16px;" title="Редактировать">'
            '✏️</button>',
            obj.id,
            obj.name,
            obj.parent.id if obj.parent else ''
        )
    edit_button.short_description = 'Действия'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('update_category/', self.admin_site.admin_view(self.update_category), name='update_category'),
        ]
        return custom_urls + urls
    
    @method_decorator(csrf_exempt)
    def update_category(self, request):
        """AJAX обновление категории"""
        if request.method == 'POST':
            try:
                category_id = request.POST.get('id')
                new_name = request.POST.get('name')
                parent_id = request.POST.get('parent')
                
                category = get_object_or_404(Category, id=category_id)
                
                # Проверка на циклическую ссылку
                if parent_id:
                    parent = get_object_or_404(Category, id=parent_id)
                    if parent.id == category.id:
                        return JsonResponse({
                            'success': False,
                            'message': 'Категория не может быть родителем самой себе'
                        })
                    category.parent = parent
                else:
                    category.parent = None
                
                category.name = new_name
                category.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Категория успешно обновлена!'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Ошибка: {str(e)}'
                })
        
        return JsonResponse({'success': False, 'message': 'Неверный метод запроса'})
    
    class Media:
        css = {
            'all': ('admin/css/category_admin.css',)
        }
        js = ('admin/js/category_admin.js',)


# Убираем отдельную админку для SubCategory, так как теперь все в Category
# @admin.register(SubCategory)
# class SubCategoryAdmin(admin.ModelAdmin):
#     ...


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'slug']
    search_fields = ['name', 'code']
    fields = ['code', 'name', 'slug', 'description', 'logo', 'meta_title', 'meta_description', 'meta_keywords']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'brand', 'catalog_number', 'artikyl_number', 'cross_number', 'price', 'stock_quantity', 'in_stock']
    list_filter = ['category', 'brand', 'in_stock', 'is_featured', 'is_new', 'created_at']
    search_fields = ['name', 'code', 'tmp_id', 'catalog_number', 'artikyl_number', 'cross_number']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductAnalogInline, OeKodInline]
    list_editable = ['price', 'stock_quantity', 'in_stock']
    actions = ['update_clean_numbers', 'link_product_images', 'delete_product_images', 'set_in_stock', 'set_out_of_stock']
    change_list_template = 'admin/shop/product/change_list.html'

    fieldsets = [
        ('Цена и наличие', {
            'fields': ['price', 'old_price', 'stock_quantity', 'in_stock'],
            'description': 'Управление ценой и остатками товара. Эти же поля можно менять прямо в списке товаров.',
        }),
        ('Основные данные', {
            'fields': ['name', 'slug', 'code', 'tmp_id', 'category', 'brand', 'catalog_number', 'artikyl_number', 'cross_number'],
        }),
        ('Очищенные номера (для поиска)', {
            'fields': ['catalog_number_clean', 'artikyl_number_clean'],
            'classes': ['collapse'],
            'description': 'Заполняются автоматически при сохранении. Можно обновить массово через действие «Обновить поисковые индексы».',
        }),
        ('Описание и применяемость', {
            'fields': ['description', 'applicability'],
        }),
        ('Пометки', {
            'fields': ['is_featured', 'is_new'],
        }),
        ('SEO', {
            'fields': ['meta_title', 'meta_description', 'meta_keywords'],
            'classes': ['collapse'],
        }),
        ('Служебные', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    readonly_fields = ['created_at', 'updated_at']
    
    def link_product_images(self, request, queryset):
        """
        Массовое действие для связывания изображений с выбранными товарами.
        Ищет изображения в папке images/{section_id}/{tmp_id}.jpg
        """
        from shop.utils.image_linker import link_images_for_products
        
        linked_count, total_count = link_images_for_products(queryset)
        
        if linked_count > 0:
            self.message_user(
                request,
                f'✅ Успешно связано {linked_count} изображений для {total_count} товаров',
                level='SUCCESS'
            )
        else:
            self.message_user(
                request,
                f'⚠️ Не найдено изображений для {total_count} товаров. Проверьте папку images/',
                level='WARNING'
            )
    
    link_product_images.short_description = '🖼️ Связать изображения с товарами'

    def delete_product_images(self, request, queryset):
        """У выбранных товаров удалить все изображения (привязки и файлы в images/)."""
        from pathlib import Path
        base = Path(settings.BASE_DIR)
        deleted_count = 0
        for product in queryset:
            for pi in product.images.all():
                path_str = getattr(pi.image, 'name', None) or str(pi.image)
                if path_str and path_str.startswith('images/'):
                    full_path = base / path_str
                    if full_path.is_file():
                        try:
                            os.remove(full_path)
                        except OSError:
                            pass
                pi.delete()
                deleted_count += 1
        self.message_user(
            request,
            f'Удалено изображений: {deleted_count}.',
            level=messages.SUCCESS
        )

    delete_product_images.short_description = '🗑️ У выбранных товаров удалить все изображения'

    def set_in_stock(self, request, queryset):
        """Отметить выбранные товары как «В наличии»."""
        updated = queryset.update(in_stock=True)
        self.message_user(request, f'Отмечено «В наличии»: {updated} товаров.', level=messages.SUCCESS)
    set_in_stock.short_description = '✅ Отметить «В наличии»'

    def set_out_of_stock(self, request, queryset):
        """Отметить выбранные товары как «Нет в наличии»."""
        updated = queryset.update(in_stock=False, stock_quantity=0)
        self.message_user(request, f'Отмечено «Нет в наличии»: {updated} товаров. Остаток обнулён.', level=messages.SUCCESS)
    set_out_of_stock.short_description = '❌ Отметить «Нет в наличии»'

    def update_clean_numbers(self, request, queryset):
        """
        Массовое действие для обновления очищенных номеров у выбранных товаров
        Полезно после ручного редактирования номеров в админке
        """
        updated_count = 0
        batch = []
        batch_size = 1000
        
        for product in queryset:
            product.catalog_number_clean = Product.clean_number(product.catalog_number)
            product.artikyl_number_clean = Product.clean_number(product.artikyl_number)
            batch.append(product)
            
            if len(batch) >= batch_size:
                Product.objects.bulk_update(
                    batch,
                    ['catalog_number_clean', 'artikyl_number_clean']
                )
                updated_count += len(batch)
                batch = []
        
        # Сохраняем остатки
        if batch:
            Product.objects.bulk_update(
                batch,
                ['catalog_number_clean', 'artikyl_number_clean']
            )
            updated_count += len(batch)
        
        self.message_user(
            request,
            f'✅ Обновлено поисковых индексов для {updated_count} товаров'
        )
    
    update_clean_numbers.short_description = '🔄 Обновить поисковые индексы (clean номера)'
    
    # Для автокомплита в других админках
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        action = 'product_updated' if change else 'product_created'
        detail = f'{getattr(obj, "name", "") or obj.pk} ({getattr(obj, "catalog_number", "")})'
        log_audit(action, user=request.user, detail=detail.strip(), object_id=obj.pk)

    def delete_model(self, request, obj):
        detail = f'{getattr(obj, "name", "") or obj.pk} ({getattr(obj, "catalog_number", "")})'
        object_id = obj.pk
        super().delete_model(request, obj)
        log_audit('product_deleted', user=request.user, detail=detail.strip(), object_id=object_id)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload_images/', self.admin_site.admin_view(self.upload_images_view), name='shop_product_upload_images'),
        ]
        return custom_urls + urls

    def upload_images_view(self, request):
        """Импорт изображений из папки: структура как в images ({section_id}/{filename}), проверка дубликатов и битых файлов."""
        from shop.utils.bulk_image_import import (
            process_bulk_image_items,
            _extract_tmp_id_and_ext,
            IMAGE_EXTENSIONS,
        )

        incoming_dir = getattr(settings, 'INCOMING_IMAGES_DIR', None) or (settings.BASE_DIR / 'incoming_images')
        incoming_str = str(incoming_dir)

        if request.method == 'POST':
            dir_exists = (incoming_dir.exists() if hasattr(incoming_dir, 'exists') else os.path.exists(incoming_dir))
            if not dir_exists:
                messages.error(
                    request,
                    f'Папка не найдена: {incoming_dir}. Создайте её и скопируйте туда файлы по SFTP/rsync.'
                )
                return HttpResponseRedirect(request.path)
            items = []
            for root, _dirs, files in os.walk(incoming_str):
                rel = os.path.relpath(root, incoming_str)
                section_id = '_imported' if rel == '.' else rel.replace('\\', '/')
                for filename in files:
                    _, ext = _extract_tmp_id_and_ext(filename)
                    if ext not in IMAGE_EXTENSIONS:
                        continue
                    path = os.path.join(root, filename)
                    if os.path.isfile(path):
                        items.append((section_id, filename, path))
            overwrite = request.POST.get('overwrite') == 'on'
            linked_count, not_found, errors, skipped_duplicates, invalid_files, restored_count = process_bulk_image_items(
                items, remove_source_if_path=True, overwrite_existing=overwrite
            )

            if linked_count > 0:
                messages.success(request, f'Привязано изображений: {linked_count}.')
            if restored_count > 0:
                messages.success(request, f'Восстановлено файлов на диске (запись в БД уже была): {restored_count}.')
            if skipped_duplicates > 0:
                messages.info(request, f'Пропущено (файл уже есть в images/): {skipped_duplicates}.')
            if invalid_files > 0:
                messages.warning(request, f'Пропущено битых или пустых файлов: {invalid_files}.')
            if not_found:
                samples = ', '.join(not_found[:10]) + ('…' if len(not_found) > 10 else '')
                messages.warning(request, f'Товар не найден для {len(not_found)} файлов (имя = tmp_id). Примеры: {samples}')
            if errors > 0:
                messages.warning(request, f'Ошибок при обработке файлов: {errors}.')
            if linked_count == 0 and restored_count == 0 and not not_found and errors == 0 and skipped_duplicates == 0 and invalid_files == 0:
                messages.info(request, 'В папке нет подходящих файлов или все уже импортированы. Структура: как в images — подпапки по section_id, имена файлов = tmp_id товара.')

            return HttpResponseRedirect(request.path)

        try:
            incoming_dir.mkdir(parents=True, exist_ok=True)
        except (AttributeError, OSError):
            pass
        incoming_path = str(incoming_dir.resolve() if hasattr(incoming_dir, 'resolve') else incoming_dir)

        return render(request, 'admin/shop/upload_images.html', {
            'title': 'Импорт изображений из папки',
            'opts': self.model._meta,
            'incoming_dir': incoming_path,
        })


@admin.register(ProductAnalog)
class ProductAnalogAdmin(admin.ModelAdmin):
    list_display = ['product', 'analog_product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['product__name', 'analog_product__name', 'product__catalog_number', 'analog_product__catalog_number']
    autocomplete_fields = ['product', 'analog_product']


@admin.register(OeKod)
class OeKodAdmin(admin.ModelAdmin):
    list_display = ['product', 'oe_kod', 'oe_kod_clean', 'id_tovar', 'brand', 'created_at']
    list_filter = ['created_at']
    search_fields = [
        'product__name', 'oe_kod', 'oe_kod_clean', 'id_tovar',
        'product__catalog_number', 'product__artikyl_number', 'product__code'
    ]
    autocomplete_fields = ['product']
    ordering = ['-created_at']


@admin.register(ImportFile)
class ImportFileAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'file_type', 'validation_status_display', 'file_type_display', 'file_size', 'uploaded_at', 'status_display', 'total_rows', 'processed_rows', 'created_products', 'action_buttons']
    list_filter = ['file_type', 'validation_status', 'status', 'processed', 'uploaded_at']
    search_fields = ['original_filename']
    ordering = ['-uploaded_at']
    
    def get_readonly_fields(self, request, obj=None):
        """Динамически определяем readonly поля"""
        if obj:  # Редактирование существующего объекта
            return ['file', 'original_filename', 'uploaded_at', 'file_info_display', 'processed', 'processed_at', 'total_rows', 'processed_rows', 'created_products', 'updated_products', 'error_log', 'cancelled', 'cancelled_at', 'validation_status', 'validation_message', 'detected_fields', 'suggested_type']
        else:  # Создание нового объекта
            return ['original_filename', 'uploaded_at', 'file_info_display', 'processed', 'processed_at', 'total_rows', 'processed_rows', 'created_products', 'updated_products', 'error_log', 'cancelled', 'cancelled_at', 'validation_status', 'validation_message', 'detected_fields', 'suggested_type']
    
    fieldsets = [
        ('Файл', {
            'fields': ['file', 'original_filename', 'file_type', 'file_info_display'],
            'description': '1️⃣ Загрузите файл → 2️⃣ Выберите тип → 3️⃣ Нажмите "Сохранить" (валидация произойдет автоматически)'
        }),
        ('✅ Результат валидации', {
            'fields': ['validation_status', 'validation_message', 'suggested_type', 'detected_fields'],
            'description': 'Валидация выполняется автоматически при сохранении файла'
        }),
        ('⚙️ Настройки импорта', {
            'fields': ['update_mode'],
            'description': '🛡️ Защита от дублирования: выберите как обрабатывать повторный импорт'
        }),
        ('Статус импорта', {
            'fields': ['status', 'processed', 'processed_at', 'uploaded_at']
        }),
        ('Прогресс', {
            'fields': ['total_rows', 'processed_rows', 'current_row', 'created_products', 'updated_products', 'error_count']
        }),
        ('Ошибки', {
            'fields': ['error_log'],
            'classes': ['collapse']
        }),
    ]
    
    # Больше не нужен JavaScript - валидация работает автоматически при сохранении
    # class Media:
    #     js = ['admin/js/import_file_validation.js']
    #     css = {
    #         'all': ['admin/css/import_file_validation.css']
    #     }
    
    def file_size(self, obj):
        """Безопасное отображение размера файла"""
        try:
            if obj.file and hasattr(obj.file, 'size'):
                size_bytes = obj.file.size
            else:
                size_bytes = 0
            
            # Конвертируем в читаемый формат
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.1f} TB"
        except Exception:
            return "Неизвестно"
    file_size.short_description = 'Размер файла'
    
    def file_type_display(self, obj):
        """Отображение типа файла"""
        return obj.file_type_display
    file_type_display.short_description = 'Тип файла'
    
    def file_info_display(self, obj):
        """Безопасное отображение информации о файле"""
        try:
            if not obj.file:
                return "Файл не загружен"
            
            info_parts = []
            
            # Имя файла
            if obj.original_filename:
                info_parts.append(f"Имя: {obj.original_filename}")
            
            # Размер файла
            try:
                if hasattr(obj.file, 'size'):
                    size_bytes = obj.file.size
                    for unit in ['B', 'KB', 'MB', 'GB']:
                        if size_bytes < 1024.0:
                            info_parts.append(f"Размер: {size_bytes:.1f} {unit}")
                            break
                        size_bytes /= 1024.0
                    else:
                        info_parts.append(f"Размер: {size_bytes:.1f} TB")
            except Exception:
                info_parts.append("Размер: Неизвестно")
            
            # Дата загрузки
            if obj.uploaded_at:
                info_parts.append(f"Загружен: {obj.uploaded_at.strftime('%d.%m.%Y %H:%M')}")
            
            # Статистика импорта
            try:
                if obj.total_rows:
                    info_parts.append(f"Всего строк: {obj.total_rows}")
                if obj.processed_rows:
                    info_parts.append(f"Обработано: {obj.processed_rows}")
                if obj.created_products:
                    info_parts.append(f"Создано товаров: {obj.created_products}")
                if obj.updated_products:
                    info_parts.append(f"Обновлено товаров: {obj.updated_products}")
            except Exception:
                pass
            
            return format_html('<br>'.join(info_parts))
        except Exception:
            return "Ошибка отображения информации"
    
    file_info_display.short_description = 'Информация о файле'
    
    def save_model(self, request, obj, form, change):
        """Автоматически заполняем original_filename и валидируем файл при сохранении"""
        import os
        
        # Если файл загружен и имя файла не установлено
        if obj.file:
            if not obj.original_filename or change:
                # Получаем имя из загруженного файла
                if hasattr(obj.file, 'name'):
                    obj.original_filename = os.path.basename(obj.file.name)
        
        # ✅ АВТОМАТИЧЕСКАЯ ВАЛИДАЦИЯ ПЕРЕД сохранением (если есть файл и тип)
        if obj.file and obj.file_type and obj.file.name:
            try:
                from shop.utils.dbf_validator import DBFValidator
                
                logger.info(f"Автоматическая валидация файла {obj.original_filename} (тип: {obj.file_type})")
                
                # Проверяем что файл существует на диске
                file_path = obj.file.path if hasattr(obj.file, 'path') else None
                if file_path and os.path.exists(file_path):
                    validator = DBFValidator()
                    result = validator.validate_file(file_path, obj.file_type)
                    
                    # Устанавливаем статус валидации ДО сохранения
                    obj.validation_status = 'valid' if result.is_valid else 'invalid'
                    obj.validation_message = result.message or ''
                    obj.detected_fields = result.found_fields or []
                    obj.suggested_type = result.suggested_type or ''
                    
                    # Показываем сообщение пользователю
                    if result.is_valid:
                        if result.warnings:
                            self.message_user(
                                request, 
                                f'⚠️ Файл валиден с предупреждениями: {result.message}. Предупреждения: {"; ".join(result.warnings)}',
                                level='warning'
                            )
                        else:
                            self.message_user(
                                request, 
                                f'✅ Файл успешно валидирован! {result.message}',
                                level='success'
                            )
                        logger.info(f"✅ Валидация успешна: {result.message}")
                    else:
                        self.message_user(
                            request, 
                            f'❌ Файл НЕ соответствует выбранному типу! {result.message}' + 
                            (f' Возможно, это файл типа: {result.suggested_type}' if result.suggested_type else ''),
                            level='error'
                        )
                        logger.error(f"❌ Валидация провалена: {result.message}")
                else:
                    logger.warning(f"Файл {obj.original_filename} еще не сохранен на диск, валидация пропущена")
                        
            except Exception as e:
                logger.error(f"Ошибка валидации файла: {e}", exc_info=True)
                self.message_user(
                    request, 
                    f'⚠️ Ошибка при валидации файла: {str(e)}',
                    level='warning'
                )
        
        # Теперь сохраняем объект со всеми полями
        super().save_model(request, obj, form, change)
    
    def total_rows(self, obj):
        """Безопасное отображение общего количества строк"""
        try:
            return obj.total_rows or 0
        except Exception:
            return 0
    
    def processed_rows(self, obj):
        """Безопасное отображение количества обработанных строк"""
        try:
            return obj.processed_rows or 0
        except Exception:
            return 0
    
    def created_products(self, obj):
        """Безопасное отображение количества созданных товаров"""
        try:
            return obj.created_products or 0
        except Exception:
            return 0
    
    def get_import_stats(self, obj):
        """Безопасное получение статистики импорта"""
        try:
            # Безопасное получение статистики
            stats = {
                'total_rows': getattr(obj, 'total_rows', 0) or 0,
                'processed_rows': getattr(obj, 'processed_rows', 0) or 0,
                'created_products': getattr(obj, 'created_products', 0) or 0,
                'updated_products': getattr(obj, 'updated_products', 0) or 0,
            }
            
            # Убеждаемся, что все значения являются числами
            for key, value in stats.items():
                try:
                    stats[key] = int(value) if value is not None else 0
                except (ValueError, TypeError):
                    stats[key] = 0
            
            return stats
        except Exception:
            # В случае любой ошибки возвращаем безопасные значения
            return {
                'total_rows': 0,
                'processed_rows': 0,
                'created_products': 0,
                'updated_products': 0,
            }
    
    def stats_display(self, obj):
        """Безопасное отображение статистики импорта"""
        try:
            stats = self.get_import_stats(obj)
            
            if stats['total_rows'] == 0:
                return "Нет данных"
            
            # Вычисляем процент выполнения
            try:
                progress_percent = min(100, int((stats['processed_rows'] / stats['total_rows']) * 100))
            except (ValueError, TypeError, ZeroDivisionError):
                progress_percent = 0
            
            # Форматируем статистику
            stats_text = f"Обработано: {stats['processed_rows']}/{stats['total_rows']} ({progress_percent}%)"
            
            if stats['created_products'] > 0:
                stats_text += f" | Создано: {stats['created_products']}"
            
            if stats['updated_products'] > 0:
                stats_text += f" | Обновлено: {stats['updated_products']}"
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 8px; border-radius: 4px; border: 1px solid #dee2e6;">{}</div>',
                stats_text
            )
        except Exception:
            return "Ошибка отображения статистики"
    
    stats_display.short_description = 'Статистика импорта'
    
    def status_display(self, obj):
        """Безопасное отображение статуса импорта"""
        try:
            status_map = {
                'pending': ('Ожидает', 'orange'),
                'processing': ('Обрабатывается', 'blue'),
                'completed': ('Завершен', 'green'),
                'failed': ('Ошибка', 'red'),
                'cancelled': ('Отменен', 'gray'),
            }
            
            status_text, color = status_map.get(obj.status, ('Неизвестно', 'gray'))
            
            # Добавляем прогресс для обрабатывающихся файлов
            if obj.status == 'processing':
                try:
                    progress = obj.progress_percent
                    status_text = f'{status_text} ({progress}%)'
                except Exception:
                    status_text = f'{status_text} (0%)'
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color, status_text
            )
        except Exception:
            return format_html(
                '<span style="color: gray; font-weight: bold;">Ошибка</span>'
            )
    status_display.short_description = 'Статус'
    
    def validation_status_display(self, obj):
        """Отображение статуса валидации с цветом"""
        try:
            status_map = {
                'pending': ('Ожидает проверки', 'orange', '⏳'),
                'valid': ('Корректна', 'green', '✅'),
                'invalid': ('Не соответствует', 'red', '❌'),
                'warning': ('Есть предупреждения', 'darkorange', '⚠️'),
            }
            
            icon, text, color = status_map.get(obj.validation_status, ('⏳', 'Неизвестно', 'gray'))
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} {}</span>',
                color, icon, text
            )
        except Exception:
            return format_html('<span style="color: gray;">-</span>')
    validation_status_display.short_description = 'Валидация'
    
    def action_buttons(self, obj):
        """Безопасное отображение кнопок действий"""
        try:
            buttons = []
            
            # Кнопка запуска импорта
            if obj.status == 'pending':
                buttons.append(
                    format_html(
                        '<a href="#" class="button btn-import-csv" data-id="{}" style="background: #28a745; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; margin-right: 5px;">▶ Запустить</a>',
                        obj.id
                    )
                )
            
            # Кнопка отмены импорта
            if obj.status == 'processing':
                buttons.append(
                    format_html(
                        '<a href="#" class="button btn-cancel-import" data-id="{}" style="background: #dc3545; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; margin-right: 5px;">⏹ Отменить</a>',
                        obj.id
                    )
                )
            
            # Кнопка просмотра прогресса
            if obj.status in ['processing', 'pending']:
                buttons.append(
                    format_html(
                        '<a href="progress/{}/" class="button" style="background: #007bff; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">📊 Прогресс</a>',
                        obj.id
                    )
                )
            
            # Кнопка повторного запуска
            if obj.status in ['failed', 'cancelled']:
                buttons.append(
                    format_html(
                        '<a href="#" class="button btn-import-csv" data-id="{}" style="background: #ffc107; color: black; padding: 5px 10px; text-decoration: none; border-radius: 3px;">🔄 Повторить</a>',
                        obj.id
                    )
                )
            
            return format_html(' '.join(buttons))
        except Exception:
            return "Ошибка отображения кнопок"
    action_buttons.short_description = 'Действия'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload/', self.admin_site.admin_view(self.upload_csv_view), name='shop_import_upload'),
            path('process/<int:file_id>/', self.admin_site.admin_view(self.process_import), name='shop_import_process'),
            path('cancel/<int:file_id>/', self.admin_site.admin_view(self.cancel_import), name='shop_import_cancel'),
            path('progress/<int:file_id>/', self.admin_site.admin_view(self.import_progress), name='shop_import_progress'),
            path('status/<int:file_id>/', self.admin_site.admin_view(self.import_status), name='shop_import_status'),
            # Валидация теперь автоматическая при сохранении, endpoint не нужен
            # path('<int:file_id>/validate/', self.admin_site.admin_view(self.validate_file), name='shop_importfile_validate'),
        ]
        return custom_urls + urls
    
    @method_decorator(csrf_exempt)
    def validate_file(self, request, file_id):
        """
        AJAX endpoint для валидации структуры DBF файла
        """
        if request.method != 'POST':
            return JsonResponse({'success': False, 'message': 'Только POST запросы'})
        
        try:
            import_file = get_object_or_404(ImportFile, id=file_id)
            
            # Проверка что выбран тип файла
            if not import_file.file_type:
                return JsonResponse({
                    'success': False,
                    'message': '❌ Сначала выберите тип файла в форме выше'
                })
            
            # Проверка что это DBF файл
            if not import_file.file.name.lower().endswith('.dbf'):
                return JsonResponse({
                    'success': False,
                    'message': '⚠️ Валидация работает только для DBF файлов'
                })
            
            # Валидация файла
            from shop.utils.dbf_validator import DBFValidator
            
            logger.info(f"Начало валидации файла {import_file.id}, тип: {import_file.file_type}")
            
            validator = DBFValidator()
            result = validator.validate_file(
                import_file.file.path,
                import_file.file_type
            )
            
            # Сохранение результатов валидации
            if result.is_valid:
                import_file.validation_status = 'warning' if result.warnings else 'valid'
            else:
                import_file.validation_status = 'invalid'
            
            import_file.validation_message = result.message
            import_file.detected_fields = result.found_fields
            import_file.suggested_type = result.suggested_type
            import_file.save()
            
            logger.info(f"Валидация завершена: {import_file.validation_status}")
            
            # Формируем ответ
            response_data = {
                'success': True,
                'is_valid': result.is_valid,
                'message': result.message,
                'validation_status': import_file.validation_status,
                'record_count': result.record_count,
                'found_fields': result.found_fields,
                'missing_fields': result.missing_fields,
                'suggested_type': result.suggested_type,
                'warnings': result.warnings,
                'errors': result.errors
            }
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Ошибка валидации: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'❌ Ошибка валидации: {str(e)}'
            })
    
    def upload_csv_view(self, request):
        """Страница загрузки CSV и DBF файлов"""
        if request.method == 'POST' and request.FILES.get('csv_file'):
            import_file = request.FILES['csv_file']
            
            # Проверяем расширение файла
            allowed_extensions = ('.csv', '.dbf')
            if not any(import_file.name.lower().endswith(ext) for ext in allowed_extensions):
                messages.error(request, 'Пожалуйста, загрузите файл с расширением .csv или .dbf')
                return HttpResponseRedirect('../')
            
            try:
                # Создаем запись импорта
                import_file_obj = ImportFile.objects.create(
                    file=import_file,
                    original_filename=import_file.name,
                    status='pending'
                )
                
                # Подсчитываем количество строк/записей в файле для отображения прогресса
                try:
                    total_rows = 0
                    
                    if import_file.name.lower().endswith('.dbf'):
                        # Обработка DBF файла
                        try:
                            from dbfread import DBF
                            table = DBF(import_file_obj.file.path, encoding='cp1251', load=False)
                            total_rows = len(table)
                        except ImportError:
                            import_file_obj.error_log = "Библиотека dbfread не установлена"
                        except Exception as e:
                            import_file_obj.error_log = f"Ошибка чтения DBF файла: {str(e)}"
                    
                    elif import_file.name.lower().endswith('.csv'):
                        # Обработка CSV файла (старая логика)
                        import csv
                        import chardet
                        
                        # Определяем кодировку
                        with open(import_file_obj.file.path, 'rb') as f:
                            raw_data = f.read()
                            result = chardet.detect(raw_data)
                            encoding = result['encoding']
                    
                        # Подсчитываем строки
                        with open(import_file_obj.file.path, 'r', encoding=encoding, errors='ignore') as f:
                            # Пробуем разные разделители
                            content = f.read()
                            if '#' in content:
                                delimiter = '#'
                            elif ';' in content:
                                delimiter = ';'
                            elif ',' in content:
                                delimiter = ','
                            else:
                                delimiter = '\t'
                            
                            f.seek(0)
                            reader = csv.DictReader(f, delimiter=delimiter)
                            total_rows = sum(1 for _ in reader)
                    
                    import_file_obj.total_rows = total_rows
                    import_file_obj.save()
                        
                except Exception as e:
                    # Если не удалось подсчитать строки, продолжаем без этого
                    import_file_obj.error_log = f"Не удалось подсчитать строки/записи: {str(e)}"
                    import_file_obj.save()
                
                file_type = "DBF" if import_file.name.lower().endswith('.dbf') else "CSV"
                log_audit('import_file_uploaded', user=request.user, detail=import_file.name, file_type=file_type, file_size=getattr(import_file, 'size', None), import_file_id=import_file_obj.id)
                messages.success(request, f'{file_type} файл "{import_file.name}" успешно загружен на сервер! Всего записей: {import_file_obj.total_rows or "неизвестно"}. Теперь можно запустить импорт.')
                return HttpResponseRedirect('../')
                
            except Exception as e:
                messages.error(request, f'Ошибка при загрузке файла: {str(e)}')
                return HttpResponseRedirect('../')
        
        return render(request, 'admin/shop/import_csv.html', {
            'title': 'Загрузка CSV файла',
            'opts': self.model._meta,
        })
    
    @method_decorator(csrf_exempt)
    def process_import(self, request, file_id):
        """AJAX обработка импорта"""
        if request.method == 'POST':
            try:
                import_file = get_object_or_404(ImportFile, id=file_id)
                
                if import_file.processed or import_file.cancelled:
                    return JsonResponse({
                        'success': False,
                        'message': 'Файл уже обработан или отменен'
                    })
                
                # Проверяем есть ли активные импорты
                active_imports = ImportFile.objects.filter(status='processing').exclude(id=file_id)
                if active_imports.exists():
                    return JsonResponse({
                        'success': False,
                        'message': 'Дождитесь завершения текущего импорта. Одновременно может выполняться только один импорт.'
                    })
                
                # ==================== НОВАЯ ПРОВЕРКА ВАЛИДАЦИИ ====================
                # Для DBF файлов проверяем валидацию
                if import_file.is_dbf_file:
                    # Проверка что выбран тип файла
                    if not import_file.file_type:
                        return JsonResponse({
                            'success': False,
                            'message': '❌ Сначала выберите тип файла и сохраните для автоматической валидации'
                        })
                    
                    # Если файл еще не валидирован - валидируем автоматически
                    if import_file.validation_status == 'pending' and import_file.file and import_file.file_type:
                        try:
                            from shop.utils.dbf_validator import DBFValidator
                            import os
                            
                            if os.path.exists(import_file.file.path):
                                validator = DBFValidator()
                                result = validator.validate_file(import_file.file.path, import_file.file_type)
                                
                                import_file.validation_status = 'valid' if result.is_valid else 'invalid'
                                import_file.validation_message = result.message or ''
                                import_file.detected_fields = result.found_fields or []
                                import_file.suggested_type = result.suggested_type or ''
                                import_file.save(update_fields=['validation_status', 'validation_message', 'detected_fields', 'suggested_type'])
                                
                                logger.info(f"Автоматическая валидация при запуске импорта: {result.message}")
                        except Exception as e:
                            logger.error(f"Ошибка автоматической валидации: {e}", exc_info=True)
                            return JsonResponse({
                                'success': False,
                                'message': f'⚠️ Ошибка валидации файла: {str(e)}'
                            })
                    
                    # Проверка что файл прошел валидацию
                    if import_file.validation_status == 'invalid':
                        return JsonResponse({
                            'success': False,
                            'message': f'❌ Файл не прошел валидацию:\n{import_file.validation_message}'
                        })
                # ==================== КОНЕЦ ПРОВЕРКИ ====================
                
                audit_user_repr = str(request.user) if request.user else '—'
                log_audit('import_started', user=request.user, detail=import_file.original_filename or (import_file.file.name if import_file.file else ''), file_type=getattr(import_file, 'file_type', None) or '—', import_file_id=import_file.id)
                
                # Запускаем импорт в отдельном потоке
                def run_import():
                    try:
                        # Обновляем статус на processing
                        import_file.status = 'processing'
                        import_file.save()
                        
                        # ==================== НОВАЯ ЛОГИКА: ИСПОЛЬЗУЕМ file_type ====================
                        if import_file.is_dbf_file and import_file.file_type:
                            # Используем тип из поля file_type (выбранный пользователем)
                            from shop.dbf_schemas import DBF_SCHEMAS
                            
                            schema = DBF_SCHEMAS.get(import_file.file_type)
                            if schema:
                                command_name = schema['command']
                                logger.info(f"Импорт типа '{import_file.file_type}' командой '{command_name}'")
                                
                                # Параметры команды зависят от типа
                                if import_file.file_type == 'products':
                                    # Только import_dbf поддерживает batch_size и update_mode
                                    call_command(
                                        command_name,
                                        import_file.file.path,
                                        batch_size=10000,
                                        disable_transactions=True,
                                        import_file_id=import_file.id,
                                        update_mode=import_file.update_mode or 'update',  # НОВОЕ!
                                    )
                                else:
                                    # import_brands_dbf и import_oe_analogs_dbf не используют batch_size
                                    call_command(
                                        command_name,
                                        import_file.file.path,
                                        import_file_id=import_file.id,
                                    )
                            else:
                                raise ValueError(f"Неизвестный тип файла: {import_file.file_type}")
                        
                        # Старая логика для DBF без типа (fallback) и CSV
                        elif import_file.is_dbf_file:
                            # Fallback: определяем по имени файла (старая логика)
                            file_name = os.path.basename(import_file.file.name).lower()
                            logger.warning(f"Тип файла не указан, определяем по имени: {file_name}")
                            
                            if 'brend' in file_name:
                                # Импорт брендов
                                logger.info(f"Импорт брендов из: {file_name}")
                                call_command(
                                    'import_brands_dbf',
                                    import_file.file.path,
                                    import_file_id=import_file.id,
                                )
                            elif 'oe_nomer' in file_name or 'oenomer' in file_name:
                                # Импорт OE аналогов
                                logger.info(f"Импорт OE аналогов из: {file_name}")
                                call_command(
                                    'import_oe_analogs_dbf',
                                    import_file.file.path,
                                    import_file_id=import_file.id,
                                )
                            else:
                                # Импорт товаров (1C*.DBF)
                                logger.info(f"Импорт товаров из: {file_name}")
                                call_command(
                                    'import_dbf',
                                    import_file.file.path,
                                    batch_size=10000,
                                    disable_transactions=True,
                                    import_file_id=import_file.id,
                                    update_mode=import_file.update_mode or 'update',  # НОВОЕ!
                                )
                        else:
                            # Используем команду для CSV файлов
                            call_command(
                                'import_products_new',
                                import_file.file.path,
                                batch_size=10000,
                                disable_transactions=True,
                                import_file_id=import_file.id,
                            )
                        
                        # Обновляем статус на completed
                        import_file.status = 'completed'
                        import_file.processed = True
                        from django.utils import timezone
                        import_file.processed_at = timezone.now()
                        import_file.save()
                        log_audit('import_completed', user_repr=audit_user_repr, detail=import_file.original_filename or (import_file.file.name if import_file.file else ''), import_file_id=import_file.id)
                        
                    except Exception as e:
                        import_file.status = 'failed'
                        import_file.error_log = traceback.format_exc()
                        import_file.save()
                        log_audit('import_failed', user_repr=audit_user_repr, detail=str(e)[:300], import_file_id=import_file.id)
                
                thread = threading.Thread(target=run_import)
                thread.daemon = True
                thread.start()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Импорт запущен в фоновом режиме.',
                    'redirect_url': f'progress/{file_id}/'
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Ошибка: {str(e)}'
                })
        
        return JsonResponse({'success': False, 'message': 'Неверный метод запроса'})
    
    @method_decorator(csrf_exempt)
    def cancel_import(self, request, file_id):
        """AJAX отмена импорта"""
        if request.method == 'POST':
            try:
                import_file = get_object_or_404(ImportFile, id=file_id)
                
                if not import_file.can_cancel:
                    return JsonResponse({
                        'success': False,
                        'message': 'Импорт нельзя отменить в текущем состоянии'
                    })
                
                # Отмечаем как отмененный
                from django.utils import timezone
                import_file.cancelled = True
                import_file.cancelled_at = timezone.now()
                import_file.status = 'cancelled'
                import_file.save()
                log_audit('import_cancelled', user=request.user, detail=import_file.original_filename or (import_file.file.name if import_file.file else ''), import_file_id=import_file.id)
                
                return JsonResponse({
                    'success': True,
                    'message': 'Импорт отменен'
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Ошибка: {str(e)}'
                })
        
        return JsonResponse({'success': False, 'message': 'Неверный метод запроса'})
    
    def import_progress(self, request, file_id):
        """Страница прогресса импорта"""
        import_file = get_object_or_404(ImportFile, id=file_id)
        
        return render(request, 'admin/shop/import_progress.html', {
            'title': f'Импорт: {import_file.original_filename}',
            'import_file': import_file,
            'opts': self.model._meta,
        })
    
    @method_decorator(csrf_exempt)
    def import_status(self, request, file_id):
        """AJAX endpoint для получения статуса импорта"""
        try:
            import_file = get_object_or_404(ImportFile, id=file_id)
            
            # Безопасное получение прогресса
            try:
                progress_percent = import_file.progress_percent
            except Exception:
                progress_percent = 0
            
            # Безопасное получение скорости обработки
            try:
                processing_speed = import_file.processing_speed
            except Exception:
                processing_speed = 0
            
            return JsonResponse({
                'success': True,
                'status': import_file.status,
                'progress_percent': progress_percent,
                'current_row': import_file.current_row,
                'total_rows': import_file.total_rows,
                'processed_rows': import_file.processed_rows,
                'created_products': import_file.created_products,
                'updated_products': import_file.updated_products,
                'error_count': import_file.error_count,
                'processing_speed': processing_speed,
                'processed': import_file.processed,
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    def error_log_display(self, obj):
        """Безопасное отображение лога ошибок"""
        try:
            if not obj.error_log:
                return "Ошибок нет"
            
            # Ограничиваем длину лога для отображения
            error_text = str(obj.error_log)
            if len(error_text) > 500:
                error_text = error_text[:500] + "..."
            
            # Форматируем ошибки для лучшего отображения
            error_lines = error_text.split('\n')
            formatted_errors = []
            
            for line in error_lines[:10]:  # Показываем только первые 10 ошибок
                if line.strip():
                    formatted_errors.append(f"• {line.strip()}")
            
            if len(error_lines) > 10:
                formatted_errors.append(f"... и еще {len(error_lines) - 10} ошибок")
            
            return format_html('<br>'.join(formatted_errors))
        except Exception:
            return "Ошибка отображения лога"
    
    error_log_display.short_description = 'Лог ошибок'
    
    class Media:
        js = ('admin/js/import_csv.js',)
        css = {
            'all': ('admin/css/import_admin.css',)
        }
