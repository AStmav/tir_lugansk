from django.contrib import admin
from django.utils.html import format_html
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
    search_fields = ['name', 'code', 'catalog_number', 'artikyl_number', 'cross_number']
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
    list_display = ['original_filename', 'uploaded_at', 'status_display', 'processed_at', 'total_rows', 'created_products', 'updated_products', 'action_buttons']
    list_filter = ['status', 'processed', 'uploaded_at']
    search_fields = ['original_filename']
    readonly_fields = ['processed', 'processed_at', 'total_rows', 'processed_rows', 'created_products', 'updated_products', 'error_log', 'cancelled', 'cancelled_at']
    ordering = ['-uploaded_at']
    
    def status_display(self, obj):
        """Отображение статуса с цветами"""
        status_colors = {
            'pending': '#ffc107',
            'processing': '#007bff',
            'completed': '#28a745',
            'failed': '#dc3545',
            'cancelled': '#6c757d',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Статус'
    
    def action_buttons(self, obj):
        """Кнопки действий"""
        buttons = []
        
        # Проверяем есть ли активные импорты
        active_imports = ImportFile.objects.filter(status='processing').exclude(id=obj.id).exists()
        
        if obj.can_start and not active_imports:
            buttons.append(
                f'<button type="button" class="btn-import-csv" data-id="{obj.id}" '
                f'style="background: #417690; color: white; border: none; padding: 5px 10px; '
                f'border-radius: 3px; cursor: pointer; margin-right: 5px;">'
                f'▶ Запустить импорт</button>'
            )
        elif obj.can_start and active_imports:
            buttons.append(
                f'<span style="color: #dc3545; font-size: 12px;">⚠ Дождитесь завершения текущего импорта</span>'
            )
        
        if obj.can_cancel:
            buttons.append(
                f'<button type="button" class="btn-cancel-import" data-id="{obj.id}" '
                f'style="background: #dc3545; color: white; border: none; padding: 5px 10px; '
                f'border-radius: 3px; cursor: pointer; margin-right: 5px;">'
                f'⏹ Отменить</button>'
            )
        
        if obj.status == 'processing':
            buttons.append(
                f'<a href="progress/{obj.id}/" style="background: #17a2b8; color: white; '
                f'text-decoration: none; padding: 5px 10px; border-radius: 3px; font-size: 12px;">'
                f'📊 Прогресс</a>'
            )
        
        if obj.processed:
            buttons.append(f'<span style="color: green; font-weight: bold;">✓ Обработан</span>')
        
        if obj.cancelled:
            buttons.append(f'<span style="color: #6c757d; font-weight: bold;">✕ Отменен</span>')
        
        return format_html(' '.join(buttons))
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
            
            # Создаем запись импорта
            import_file = ImportFile.objects.create(
                file=csv_file,
                original_filename=csv_file.name
            )
            
            messages.success(request, f'Файл "{csv_file.name}" успешно загружен. Теперь можно запустить импорт.')
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
                
                # Обновляем статус на processing
                import_file.status = 'processing'
                import_file.save()
                
                # Запускаем импорт в отдельном потоке
                def run_import():
                    try:
                        call_command('import_csv', file_id=file_id)
                    except Exception as e:
                        import_file.status = 'failed'
                        import_file.error_log = str(e)
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
            
            return JsonResponse({
                'success': True,
                'status': import_file.status,
                'progress_percent': import_file.progress_percent,
                'current_row': import_file.current_row,
                'total_rows': import_file.total_rows,
                'processed_rows': import_file.processed_rows,
                'created_products': import_file.created_products,
                'updated_products': import_file.updated_products,
                'error_count': import_file.error_count,
                'processing_speed': import_file.processing_speed,
                'processed': import_file.processed,
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    class Media:
        js = ('admin/js/import_csv.js',)
