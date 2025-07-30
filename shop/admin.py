from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
from .models import Category, SubCategory, Brand, Product, ProductImage, ProductAnalog


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductAnalogInline(admin.TabularInline):
    model = ProductAnalog
    fk_name = 'product'
    extra = 1
    verbose_name = 'Аналог'
    verbose_name_plural = 'Аналоги'


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
    list_display = ['name', 'category', 'brand', 'price', 'in_stock', 'is_featured', 'is_new']
    list_filter = ['category', 'brand', 'in_stock', 'is_featured', 'is_new', 'created_at']
    search_fields = ['name', 'code', 'catalog_number']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductAnalogInline]
    list_editable = ['price', 'in_stock', 'is_featured', 'is_new']


@admin.register(ProductAnalog)
class ProductAnalogAdmin(admin.ModelAdmin):
    list_display = ['product', 'analog_product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['product__name', 'analog_product__name', 'product__catalog_number', 'analog_product__catalog_number']
    autocomplete_fields = ['product', 'analog_product']
