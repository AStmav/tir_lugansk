from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.text import slugify
from django.utils import timezone
from django.urls import reverse


class Page(models.Model):
    PAGE_TYPES = [
        ('about', 'О компании'),
        ('contacts', 'Контакты'),
        ('home', 'Главная'),
        ('custom', 'Пользовательская'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='Заголовок')
    slug = models.SlugField(unique=True, verbose_name='URL')
    page_type = models.CharField(max_length=20, choices=PAGE_TYPES, default='custom', verbose_name='Тип страницы')
    content = models.TextField(verbose_name='Содержимое', help_text='HTML контент страницы')
    meta_title = models.CharField(max_length=200, blank=True, verbose_name='Meta заголовок')
    meta_description = models.TextField(blank=True, verbose_name='Meta описание')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    
    class Meta:
        verbose_name = 'Страница'
        verbose_name_plural = 'Страницы'
        ordering = ['title']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class ContentBlock(models.Model):
    BLOCK_TYPES = [
        ('text', 'Текстовый блок'),
        ('image', 'Изображение'),
        ('contact', 'Контактная информация'),
        ('team', 'Команда'),
        ('reviews', 'Отзывы'),
        ('html', 'HTML блок'),
    ]
    
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='blocks', verbose_name='Страница')
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPES, verbose_name='Тип блока')
    title = models.CharField(max_length=200, blank=True, verbose_name='Заголовок')
    content = models.TextField(verbose_name='Содержимое')
    image = models.ImageField(upload_to='content_blocks/', blank=True, null=True, verbose_name='Изображение')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    
    class Meta:
        verbose_name = 'Блок контента'
        verbose_name_plural = 'Блоки контента'
        ordering = ['page', 'order']
    
    def __str__(self):
        return f"{self.page.title} - {self.get_block_type_display()}"


class HeaderNotice(models.Model):
    LEVEL_INFO = "info"
    LEVEL_WARNING = "warning"
    LEVEL_CRITICAL = "critical"
    LEVEL_CHOICES = [
        (LEVEL_INFO, "Информация"),
        (LEVEL_WARNING, "Предупреждение"),
        (LEVEL_CRITICAL, "Критично"),
    ]

    title = models.CharField(max_length=120, blank=True, verbose_name="Заголовок")
    message = models.CharField(max_length=280, verbose_name="Текст сообщения")
    link_url = models.URLField(blank=True, verbose_name="Ссылка")
    link_text = models.CharField(max_length=60, blank=True, verbose_name="Текст ссылки")
    level = models.CharField(
        max_length=16,
        choices=LEVEL_CHOICES,
        default=LEVEL_INFO,
        verbose_name="Уровень важности",
    )
    is_active = models.BooleanField(default=False, verbose_name="Включено")
    starts_at = models.DateTimeField(null=True, blank=True, verbose_name="Показывать с")
    ends_at = models.DateTimeField(null=True, blank=True, verbose_name="Показывать до")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Важное сообщение в шапке"
        verbose_name_plural = "Важные сообщения в шапке"
        ordering = ["-is_active", "-updated_at"]

    def __str__(self):
        return self.title or self.message[:60]

    def clean(self):
        super().clean()
        if self.ends_at and self.starts_at and self.ends_at < self.starts_at:
            raise ValidationError({"ends_at": "Дата окончания не может быть раньше даты начала."})
        if self.link_url and not self.link_text:
            raise ValidationError({"link_text": "Укажите текст ссылки."})


class HelpfulMenuItem(models.Model):
    title = models.CharField(max_length=80, verbose_name="Название")
    useful_category = models.ForeignKey(
        "UsefulCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="menu_items",
        verbose_name="Категория полезного",
    )
    url = models.CharField(
        max_length=500,
        verbose_name="Ссылка",
        help_text="Внутренний путь (/news/) или полный URL (https://...).",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    open_in_new_tab = models.BooleanField(default=False, verbose_name="Открывать в новой вкладке")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Пункт меню «Полезное»"
        verbose_name_plural = "Пункты меню «Полезное»"
        ordering = ["order", "title"]

    def __str__(self):
        return self.title


class UsefulCategory(models.Model):
    title = models.CharField(max_length=120, verbose_name="Название категории")
    slug = models.SlugField(unique=True, verbose_name="Slug")
    description = models.TextField(blank=True, verbose_name="Описание")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Категория раздела «Полезное»"
        verbose_name_plural = "Категории раздела «Полезное»"
        ordering = ["order", "title"]

    def __str__(self):
        return self.title


class UsefulPost(models.Model):
    category = models.ForeignKey(
        UsefulCategory,
        on_delete=models.CASCADE,
        related_name="posts",
        verbose_name="Категория",
    )
    title = models.CharField(max_length=180, verbose_name="Заголовок")
    summary = models.TextField(blank=True, verbose_name="Краткое описание")
    content = models.TextField(blank=True, verbose_name="Содержимое")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    published_at = models.DateTimeField(default=timezone.now, verbose_name="Дата публикации")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Материал раздела «Полезное»"
        verbose_name_plural = "Материалы раздела «Полезное»"
        ordering = ["-published_at", "order", "title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("pages:useful_post_detail", kwargs={"post_id": self.id})


class Contact(models.Model):
    name = models.CharField(max_length=100, verbose_name='Имя')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    email = models.EmailField(blank=True, verbose_name='Email')
    message = models.TextField(blank=True, verbose_name='Сообщение')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    is_processed = models.BooleanField(default=False, verbose_name='Обработано')
    
    class Meta:
        verbose_name = 'Заявка на звонок'
        verbose_name_plural = 'Заявки на звонок'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.phone}"


class PriceInquiry(models.Model):
    REQUEST_TYPES = [
        ('call', 'Заявка на звонок'),
        ('price', 'Запрос цены товара'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Имя')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    email = models.EmailField(blank=True, verbose_name='Email')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    request_type = models.CharField(max_length=10, choices=REQUEST_TYPES, default='call', verbose_name='Тип заявки')
    
    # Поля для запроса цены товара (необязательные)
    product_id = models.CharField(max_length=50, blank=True, verbose_name='ID товара')
    product_name = models.CharField(max_length=255, blank=True, verbose_name='Название товара')
    product_code = models.CharField(max_length=100, blank=True, verbose_name='Код товара')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    is_processed = models.BooleanField(default=False, verbose_name='Обработано')
    
    class Meta:
        verbose_name = 'Заявка на звонок'
        verbose_name_plural = 'Заявки на звонок'
        ordering = ['-created_at']
    
    def __str__(self):
        if self.request_type == 'price' and self.product_name:
            return f"{self.name} - {self.product_name}"
        return f"{self.name} - {self.get_request_type_display()}"


class NotificationRecipient(models.Model):
    CHANNEL_EMAIL = "email"
    CHANNEL_TELEGRAM = "telegram"
    CHANNEL_MAX = "max"
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_TELEGRAM, "Telegram"),
        (CHANNEL_MAX, "MAX"),
    ]

    channel = models.CharField(
        max_length=16,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_EMAIL,
        verbose_name="Канал",
    )
    value = models.CharField(
        max_length=255,
        verbose_name="Получатель",
        help_text="Email адрес или идентификатор канала (например chat_id).",
    )
    bot_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Bot token",
        help_text="Для Telegram: токен бота (если не указан, используется из .env).",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    note = models.CharField(max_length=255, blank=True, verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлен")

    class Meta:
        verbose_name = "Получатель уведомлений"
        verbose_name_plural = "Получатели уведомлений"
        ordering = ["channel", "value"]
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "value"],
                name="pages_notification_recipient_channel_value_uq",
            )
        ]

    def __str__(self):
        return f"{self.get_channel_display()}: {self.value}"

    def clean(self):
        super().clean()
        if self.channel == self.CHANNEL_EMAIL:
            try:
                validate_email(self.value)
            except ValidationError as exc:
                raise ValidationError({"value": "Введите корректный email адрес."}) from exc
        elif self.channel == self.CHANNEL_TELEGRAM:
            raw = (self.value or "").strip()
            if not raw:
                raise ValidationError({"value": "Для Telegram укажите chat_id."})
            if raw.startswith("@"):
                if len(raw) < 2:
                    raise ValidationError({"value": "Некорректный Telegram username."})
            else:
                test_raw = raw[1:] if raw.startswith("-") else raw
                if not test_raw.isdigit():
                    raise ValidationError(
                        {"value": "Telegram chat_id должен быть числом (например -1001234567890)."}
                    )
            # Для текущего проекта используем один Telegram-канал и один бот.
            # Не допускаем создание нескольких Telegram-получателей.
            qs = NotificationRecipient.objects.filter(channel=self.CHANNEL_TELEGRAM)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"channel": "Разрешена только одна Telegram-настройка (один канал и один бот)."}
                )
        elif self.channel == self.CHANNEL_MAX:
            raw = (self.value or "").strip()
            if not raw:
                raise ValidationError({"value": "Для MAX укажите OWNER_ID."})
            test_raw = raw[1:] if raw.startswith("-") else raw
            if not test_raw.isdigit():
                raise ValidationError({"value": "MAX OWNER_ID должен быть числом."})
            if not (self.bot_token or "").strip():
                raise ValidationError({"bot_token": "Для MAX укажите BOT_TOKEN."})

            # Для текущего проекта используем один MAX-канал и один бот.
            qs = NotificationRecipient.objects.filter(channel=self.CHANNEL_MAX)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"channel": "Разрешена только одна MAX-настройка (один owner и один бот)."}
                )


class EmailNotificationRecipient(NotificationRecipient):
    class Meta:
        proxy = True
        verbose_name = "Получатель Email"
        verbose_name_plural = "Получатели Email"


class TelegramNotificationRecipient(NotificationRecipient):
    class Meta:
        proxy = True
        verbose_name = "Телеграм канал / Телеграм Бот"
        verbose_name_plural = "Телеграм канал / Телеграм Бот"


class MaxNotificationRecipient(NotificationRecipient):
    class Meta:
        proxy = True
        verbose_name = "MAX канал / MAX Бот"
        verbose_name_plural = "MAX канал / MAX Бот"


class NotificationDelivery(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Ожидает"),
        (STATUS_SENT, "Отправлено"),
        (STATUS_FAILED, "Ошибка"),
        (STATUS_SKIPPED, "Пропущено"),
    ]

    inquiry = models.ForeignKey(
        PriceInquiry,
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
        verbose_name="Заявка",
    )
    channel = models.CharField(max_length=16, verbose_name="Канал")
    recipient = models.CharField(max_length=255, verbose_name="Получатель")
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="Статус",
    )
    attempt_count = models.PositiveIntegerField(default=0, verbose_name="Попыток")
    last_error = models.TextField(blank=True, verbose_name="Последняя ошибка")
    idempotency_key = models.CharField(max_length=255, unique=True, verbose_name="Idempotency key")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Время успешной отправки")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Лог доставки уведомления"
        verbose_name_plural = "Логи доставки уведомлений"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["channel", "status"], name="pg_notif_del_ch_st_idx"),
            models.Index(fields=["inquiry", "status"], name="pg_notif_del_inq_st_idx"),
        ]

    def __str__(self):
        return f"{self.inquiry_id} | {self.channel} | {self.status} | {self.recipient}"
