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
from .models import Category, SubCategory, Brand, Product, ProductImage, ProductAnalog, OeKod, ImportFile


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
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'brand', 'catalog_number', 'artikyl_number', 'cross_number', 'price', 'in_stock']
    list_filter = ['category', 'brand', 'in_stock', 'is_featured', 'is_new', 'created_at']
    search_fields = ['name', 'code', 'tmp_id', 'catalog_number', 'artikyl_number', 'cross_number']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductAnalogInline, OeKodInline]
    list_editable = ['price', 'in_stock']
    # Для автокомплита в других админках
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct


@admin.register(ProductAnalog)
class ProductAnalogAdmin(admin.ModelAdmin):
    list_display = ['product', 'analog_product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['product__name', 'analog_product__name', 'product__catalog_number', 'analog_product__catalog_number']
    autocomplete_fields = ['product', 'analog_product']


@admin.register(OeKod)
class OeKodAdmin(admin.ModelAdmin):
    list_display = ['product', 'oe_kod', 'created_at']
    list_filter = ['created_at']
    search_fields = ['product__name', 'oe_kod', 'product__catalog_number', 'product__artikyl_number']
    autocomplete_fields = ['product']
    ordering = ['-created_at']


@admin.register(ImportFile)
class ImportFileAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'file_size', 'uploaded_at', 'status_display', 'total_rows', 'processed_rows', 'created_products', 'action_buttons']
    list_filter = ['status', 'processed', 'uploaded_at']
    search_fields = ['original_filename']
    readonly_fields = ['file', 'original_filename', 'uploaded_at', 'file_info_display', 'processed', 'processed_at', 'total_rows', 'processed_rows', 'created_products', 'updated_products', 'error_log', 'cancelled', 'cancelled_at']
    ordering = ['-uploaded_at']
    
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
        ]
        return custom_urls + urls
    
    def upload_csv_view(self, request):
        """Страница загрузки CSV файла"""
        if request.method == 'POST' and request.FILES.get('csv_file'):
            csv_file = request.FILES['csv_file']
            
            # Проверяем расширение файла
            if not csv_file.name.lower().endswith('.csv'):
                messages.error(request, 'Пожалуйста, загрузите файл с расширением .csv')
                return HttpResponseRedirect('../')
            
            try:
                # Создаем запись импорта
                import_file = ImportFile.objects.create(
                    file=csv_file,
                    original_filename=csv_file.name,
                    status='pending'
                )
                
                # Подсчитываем количество строк в файле для отображения прогресса
                try:
                    import csv
                    import chardet
                    
                    # Определяем кодировку
                    with open(import_file.file.path, 'rb') as f:
                        raw_data = f.read()
                        result = chardet.detect(raw_data)
                        encoding = result['encoding']
                    
                    # Подсчитываем строки
                    with open(import_file.file.path, 'r', encoding=encoding, errors='ignore') as f:
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
                        
                        import_file.total_rows = total_rows
                        import_file.save()
                        
                except Exception as e:
                    # Если не удалось подсчитать строки, продолжаем без этого
                    import_file.error_log = f"Не удалось подсчитать строки: {str(e)}"
                    import_file.save()
                
                messages.success(request, f'Файл "{csv_file.name}" успешно загружен на сервер! Всего строк: {import_file.total_rows or "неизвестно"}. Теперь можно запустить импорт.')
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
                
                # Запускаем импорт в отдельном потоке
                def run_import():
                    try:
                        # Обновляем статус на processing
                        import_file.status = 'processing'
                        import_file.save()
                        
                        # Используем новую команду import_products_new с загруженным файлом
                        call_command(
                            'import_products_new',
                            import_file.file.path,  # positional csv_file
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
                        
                    except Exception as e:
                        import_file.status = 'failed'
                        import_file.error_log = traceback.format_exc()
                        import_file.save()
                
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
