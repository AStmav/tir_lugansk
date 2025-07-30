from django.db import models
from django.utils.text import slugify


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
