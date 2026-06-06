from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from .models import (
    Page,
    ContentBlock,
    HeaderNotice,
    HelpfulMenuItem,
    UsefulCategory,
    UsefulPost,
    PriceInquiry,
    NotificationRecipient,
    NotificationDelivery,
    EmailNotificationRecipient,
    TelegramNotificationRecipient,
    MaxNotificationRecipient,
)


class ContentBlockInlineForm(forms.ModelForm):
    class Meta:
        model = ContentBlock
        fields = ['block_type', 'title', 'content', 'image', 'order', 'is_active']
        widgets = {
            'content': CKEditorUploadingWidget(),
        }


class ContentBlockInline(admin.StackedInline):
    model = ContentBlock
    form = ContentBlockInlineForm
    extra = 1
    fields = ['block_type', 'title', 'content', 'image', 'order', 'is_active']


class PageAdminForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = '__all__'
        widgets = {
            'content': CKEditorUploadingWidget(),
        }


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    form = PageAdminForm
    list_display = ['title', 'page_type', 'slug', 'is_active', 'created_at', 'updated_at', 'preview_link']
    list_filter = ['page_type', 'is_active', 'created_at']
    search_fields = ['title', 'content', 'meta_title']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['created_at', 'updated_at', 'preview_link']
    inlines = [ContentBlockInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'slug', 'page_type', 'is_active'),
            'description': (
                'Одна страница по адресу /page/slug/ (например /page/codestmc/). '
                'Для раздела с несколькими материалами используйте «Категории полезного» (/useful/slug/).'
            ),
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Содержимое', {
            'fields': ('content',),
            'description': 'Визуальный редактор: форматирование, ссылки, таблицы и загрузка изображений.',
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


class ContentBlockAdminForm(forms.ModelForm):
    class Meta:
        model = ContentBlock
        fields = '__all__'
        widgets = {
            'content': CKEditorUploadingWidget(),
        }


@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    form = ContentBlockAdminForm
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
            'description': 'Текст блока — в визуальном редакторе (ссылки, таблицы, картинки). Отдельное поле «Изображение» — для типов блоков с одной картинкой.',
        }),
        ('Системная информация', {
            'fields': ('order', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at']


@admin.register(HeaderNotice)
class HeaderNoticeAdmin(admin.ModelAdmin):
    class HeaderNoticeForm(forms.ModelForm):
        class Meta:
            model = HeaderNotice
            fields = "__all__"
            widgets = {
                "message": forms.Textarea(
                    attrs={
                        "rows": 5,
                        "style": "max-width: 90ch; width: 100%;",
                        "placeholder": "Введите текст сообщения (можно в несколько строк)…",
                    }
                )
            }

    form = HeaderNoticeForm
    list_display = ["display_name", "level", "is_active", "starts_at", "ends_at", "updated_at"]
    list_filter = ["is_active", "level"]
    search_fields = ["title", "message", "link_text", "link_url"]
    list_editable = ["is_active"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-is_active", "-updated_at"]

    fieldsets = (
        ("Контент", {"fields": ("title", "message", "level")}),
        ("Ссылка", {"fields": ("link_url", "link_text"), "classes": ("collapse",)}),
        ("Публикация", {"fields": ("is_active", "starts_at", "ends_at")}),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def display_name(self, obj):
        return obj.title or obj.message[:60]

    display_name.short_description = "Сообщение"


@admin.register(HelpfulMenuItem)
class HelpfulMenuItemAdmin(admin.ModelAdmin):
    list_display = ["title", "useful_category", "url", "order", "is_active", "open_in_new_tab", "updated_at"]
    list_editable = ["order", "is_active", "open_in_new_tab"]
    list_filter = ["is_active", "open_in_new_tab", "useful_category"]
    search_fields = ["title", "url", "useful_category__title"]
    ordering = ["order", "title"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Пункт меню",
            {
                "fields": ("title", "useful_category", "url", "order", "is_active", "open_in_new_tab"),
                "description": (
                    "Категория полезного → /slug/ (ссылка подставится из категории). "
                    "Страница из раздела «Страницы» → URL вручную, например /page/codestmc/ "
                    "(категорию оставьте пустой)."
                ),
            },
        ),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class UsefulPostInlineForm(forms.ModelForm):
    class Meta:
        model = UsefulPost
        fields = ("title", "summary", "order", "is_active", "published_at")
        widgets = {
            "summary": CKEditorUploadingWidget(),
        }


class UsefulPostInline(admin.StackedInline):
    model = UsefulPost
    form = UsefulPostInlineForm
    extra = 0
    fields = ("title", "summary", "order", "is_active", "published_at")
    ordering = ("-published_at", "order")


class UsefulCategoryAdminForm(forms.ModelForm):
    class Meta:
        model = UsefulCategory
        fields = '__all__'
        widgets = {
            'description': CKEditorUploadingWidget(),
        }


@admin.register(UsefulCategory)
class UsefulCategoryAdmin(admin.ModelAdmin):
    form = UsefulCategoryAdminForm
    list_display = ("title", "slug", "posts_per_page", "order", "is_active", "updated_at")
    list_editable = ("order", "is_active")
    search_fields = ("title", "slug", "description")
    ordering = ("order", "title")
    readonly_fields = ("created_at", "updated_at")
    inlines = [UsefulPostInline]
    prepopulated_fields = {"slug": ("title",)}

    fieldsets = (
        (
            "Основное",
            {
                "fields": ("title", "slug", "description", "posts_per_page", "order", "is_active"),
                "description": (
                    "Список материалов открывается по адресу /slug/ (например /news/, /codestmc/). "
                    "Старый путь /useful/slug/ перенаправляется автоматически. "
                    "Одна большая HTML-страница — модель «Страницы» (/page/slug/)."
                ),
            },
        ),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class UsefulPostAdminForm(forms.ModelForm):
    class Meta:
        model = UsefulPost
        fields = '__all__'
        widgets = {
            'summary': CKEditorUploadingWidget(),
            'content': CKEditorUploadingWidget(),
        }


@admin.register(UsefulPost)
class UsefulPostAdmin(admin.ModelAdmin):
    form = UsefulPostAdminForm
    list_display = ("title", "category", "published_at", "order", "is_active", "updated_at")
    list_editable = ("order", "is_active")
    list_filter = ("category", "is_active", "published_at")
    search_fields = ("title", "summary", "content", "category__title")
    ordering = ("-published_at", "order")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Материал",
            {"fields": ("category", "title", "summary", "content", "published_at", "order", "is_active")},
        ),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class DeliveryErrorFilter(admin.SimpleListFilter):
    title = "ошибки доставки"
    parameter_name = "delivery_errors"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Есть ошибки"),
            ("no", "Без ошибок"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                notification_deliveries__status=NotificationDelivery.STATUS_FAILED
            ).distinct()
        if self.value() == "no":
            return queryset.exclude(
                notification_deliveries__status=NotificationDelivery.STATUS_FAILED
            ).distinct()
        return queryset


@admin.register(PriceInquiry)
class PriceInquiryAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'phone',
        'email',
        'request_type',
        'product_name_short',
        'delivery_summary',
        'is_processed',
        'created_at',
    ]
    list_filter = [
        ('is_processed', admin.BooleanFieldListFilter),
        ('request_type', admin.ChoicesFieldListFilter),
        DeliveryErrorFilter,
    ]
    search_fields = ['name', 'phone', 'email', 'comment', 'product_name', 'product_code']
    readonly_fields = ['created_at', 'consent_at']
    list_editable = ['is_processed']
    
    def get_list_filter(self, request):
        """Переопределяем фильтры для простого отображения"""
        return [
            ('is_processed', admin.BooleanFieldListFilter),
            ('request_type', admin.ChoicesFieldListFilter),
            DeliveryErrorFilter,
        ]
    
    def product_name_short(self, obj):
        if obj.product_name:
            return obj.product_name[:50] + '...' if len(obj.product_name) > 50 else obj.product_name
        return '-'
    product_name_short.short_description = 'Товар'

    def delivery_summary(self, obj):
        sent = obj.notification_deliveries.filter(status=NotificationDelivery.STATUS_SENT).count()
        failed = obj.notification_deliveries.filter(status=NotificationDelivery.STATUS_FAILED).count()
        skipped = obj.notification_deliveries.filter(status=NotificationDelivery.STATUS_SKIPPED).count()
        return f"ok:{sent} err:{failed} skip:{skipped}"
    delivery_summary.short_description = 'Доставка'
    
    fieldsets = (
        ('Контактная информация', {
            'fields': ('name', 'phone', 'email', 'comment', 'request_type', 'personal_data_consent', 'consent_at')
        }),
        ('Информация о товаре', {
            'fields': ('product_name', 'product_code', 'product_id'),
            'classes': ('collapse',),
            'description': 'Заполняется автоматически для запросов цены товара'
        }),
        ('Статус', {
            'fields': ('is_processed',)
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_processed', 'mark_as_unprocessed']
    
    def mark_as_processed(self, request, queryset):
        updated = queryset.update(is_processed=True)
        self.message_user(request, f'{updated} заявок отмечено как обработанные.')
    mark_as_processed.short_description = 'Отметить как обработанные'
    
    def mark_as_unprocessed(self, request, queryset):
        updated = queryset.update(is_processed=False)
        self.message_user(request, f'{updated} заявок отмечено как необработанные.')
    mark_as_unprocessed.short_description = 'Отметить как необработанные'


class BaseNotificationRecipientAdmin(admin.ModelAdmin):
    list_display = ["channel", "value", "is_active", "has_bot_token", "note", "updated_at"]
    list_filter = ["channel", "is_active"]
    search_fields = ["value", "note"]
    list_editable = ["is_active"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["channel", "value"]

    fieldsets = (
        ("Основное", {"fields": ("channel", "value", "bot_token", "is_active", "note")}),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def has_bot_token(self, obj):
        return bool(obj.bot_token)

    actions = ["activate_selected", "deactivate_selected"]

    has_bot_token.boolean = True
    has_bot_token.short_description = "Токен"

    def activate_selected(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Активировано получателей: {updated}.")
    activate_selected.short_description = "Включить выбранных получателей"

    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Деактивировано получателей: {updated}.")
    deactivate_selected.short_description = "Выключить выбранных получателей"


class _ForcedChannelRecipientForm(forms.ModelForm):
    forced_channel = None

    def clean(self):
        cleaned = super().clean()
        if self.forced_channel:
            self.instance.channel = self.forced_channel
        return cleaned


class EmailNotificationRecipientForm(_ForcedChannelRecipientForm):
    forced_channel = NotificationRecipient.CHANNEL_EMAIL

    class Meta:
        model = EmailNotificationRecipient
        fields = "__all__"


class TelegramNotificationRecipientForm(_ForcedChannelRecipientForm):
    forced_channel = NotificationRecipient.CHANNEL_TELEGRAM

    class Meta:
        model = TelegramNotificationRecipient
        fields = "__all__"


class MaxNotificationRecipientForm(_ForcedChannelRecipientForm):
    forced_channel = NotificationRecipient.CHANNEL_MAX

    class Meta:
        model = MaxNotificationRecipient
        fields = "__all__"


@admin.register(EmailNotificationRecipient)
class EmailNotificationRecipientAdmin(BaseNotificationRecipientAdmin):
    form = EmailNotificationRecipientForm
    list_display = ["value", "is_active", "note", "updated_at"]
    list_filter = ["is_active"]
    fieldsets = (
        ("Email получатель", {"fields": ("value", "is_active", "note")}),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(channel=NotificationRecipient.CHANNEL_EMAIL)

    def save_model(self, request, obj, form, change):
        obj.channel = NotificationRecipient.CHANNEL_EMAIL
        obj.bot_token = ""
        super().save_model(request, obj, form, change)


@admin.register(TelegramNotificationRecipient)
class TelegramNotificationRecipientAdmin(BaseNotificationRecipientAdmin):
    form = TelegramNotificationRecipientForm
    list_display = ["telegram_channel", "has_bot_token", "is_active", "note", "updated_at"]
    list_filter = []
    search_fields = []
    ordering = ["-updated_at"]
    fieldsets = (
        ("Телеграм канал", {"fields": ("value", "bot_token", "is_active", "note")}),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(channel=NotificationRecipient.CHANNEL_TELEGRAM)

    def save_model(self, request, obj, form, change):
        obj.channel = NotificationRecipient.CHANNEL_TELEGRAM
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        # В проекте используется только один Telegram-канал.
        if NotificationRecipient.objects.filter(channel=NotificationRecipient.CHANNEL_TELEGRAM).exists():
            return False
        return super().has_add_permission(request)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "value" in form.base_fields:
            form.base_fields["value"].help_text = "Идентификатор канала (chat_id)."
        return form

    def telegram_channel(self, obj):
        return obj.value

    telegram_channel.short_description = "Телеграм канал"


@admin.register(MaxNotificationRecipient)
class MaxNotificationRecipientAdmin(BaseNotificationRecipientAdmin):
    form = MaxNotificationRecipientForm
    list_display = ["max_owner_id", "has_bot_token", "is_active", "note", "updated_at"]
    list_filter = []
    search_fields = []
    ordering = ["-updated_at"]
    fieldsets = (
        ("MAX канал", {"fields": ("value", "bot_token", "is_active", "note")}),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(channel=NotificationRecipient.CHANNEL_MAX)

    def save_model(self, request, obj, form, change):
        obj.channel = NotificationRecipient.CHANNEL_MAX
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        if NotificationRecipient.objects.filter(channel=NotificationRecipient.CHANNEL_MAX).exists():
            return False
        return super().has_add_permission(request)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "value" in form.base_fields:
            form.base_fields["value"].help_text = "OWNER_ID (числовой идентификатор владельца)."
        if "bot_token" in form.base_fields:
            form.base_fields["bot_token"].help_text = "BOT_TOKEN для MAX."
        return form

    def max_owner_id(self, obj):
        return obj.value

    max_owner_id.short_description = "MAX OWNER_ID"


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        "inquiry",
        "channel",
        "recipient",
        "status",
        "attempt_count",
        "sent_at",
        "updated_at",
    ]
    list_filter = ["channel", "status", "sent_at", "updated_at"]
    search_fields = ["recipient", "idempotency_key", "inquiry__name", "inquiry__phone"]
    readonly_fields = [
        "inquiry",
        "channel",
        "recipient",
        "status",
        "attempt_count",
        "last_error",
        "idempotency_key",
        "sent_at",
        "created_at",
        "updated_at",
    ]
    ordering = ["-updated_at"]
