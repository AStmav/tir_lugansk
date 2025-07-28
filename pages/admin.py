from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Page, Contact, ContentBlock


class ContentBlockInline(admin.TabularInline):
    model = ContentBlock
    extra = 1
    fields = ['block_type', 'title', 'content', 'image', 'order', 'is_active']


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ['title', 'page_type', 'slug', 'is_active', 'created_at', 'updated_at', 'preview_link']
    list_filter = ['page_type', 'is_active', 'created_at']
    search_fields = ['title', 'content', 'meta_title']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['created_at', 'updated_at', 'preview_link']
    inlines = [ContentBlockInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'slug', 'page_type', 'is_active')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Содержимое', {
            'fields': ('content',),
            'description': 'Используйте HTML теги для форматирования. Например: <h2>Заголовок</h2>, <p>Параграф</p>'
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def preview_link(self, obj):
        if obj.is_active:
            return format_html(
                '<a href="{}" target="_blank">Просмотр</a>',
                reverse('pages:page_detail', args=[obj.slug])
            )
        return 'Неактивна'
    preview_link.short_description = 'Просмотр'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()
    
    class Media:
        css = {
            'all': ('admin/css/page_admin.css',)
        }
        js = ('admin/js/page_admin.js',)


@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    list_display = ['page', 'block_type', 'title', 'order', 'is_active', 'created_at']
    list_filter = ['block_type', 'is_active', 'page', 'created_at']
    search_fields = ['title', 'content', 'page__title']
    list_editable = ['order', 'is_active']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('page', 'block_type', 'title', 'is_active')
        }),
        ('Содержимое', {
            'fields': ('content', 'image'),
            'description': 'Для HTML блоков используйте HTML теги. Для текстовых блоков - обычный текст.'
        }),
        ('Системная информация', {
            'fields': ('order', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at']


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'is_processed', 'created_at', 'short_message']
    list_filter = ['is_processed', 'created_at']
    search_fields = ['name', 'phone', 'email', 'message']
    readonly_fields = ['created_at']
    list_editable = ['is_processed']
    
    fieldsets = (
        ('Контактная информация', {
            'fields': ('name', 'phone', 'email')
        }),
        ('Сообщение', {
            'fields': ('message',)
        }),
        ('Статус', {
            'fields': ('is_processed',)
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def short_message(self, obj):
        if obj.message:
            return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
        return '-'
    short_message.short_description = 'Сообщение'
    
    actions = ['mark_as_processed', 'mark_as_unprocessed']
    
    def mark_as_processed(self, request, queryset):
        updated = queryset.update(is_processed=True)
        self.message_user(request, f'{updated} заявок отмечено как обработанные.')
    mark_as_processed.short_description = 'Отметить как обработанные'
    
    def mark_as_unprocessed(self, request, queryset):
        updated = queryset.update(is_processed=False)
        self.message_user(request, f'{updated} заявок отмечено как необработанные.')
    mark_as_unprocessed.short_description = 'Отметить как необработанные'
