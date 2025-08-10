from django.db import models
from django.urls import reverse
import re


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    slug = models.SlugField(unique=True, verbose_name='URL')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, related_name='children', blank=True, null=True, verbose_name='Родительская категория')
    description = models.TextField(blank=True, verbose_name='Описание')
    image = models.ImageField(upload_to='categories/', blank=True, verbose_name='Изображение')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок сортировки')
    
    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['order', 'name']
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name
    
    def get_absolute_url(self):
        return reverse('shop:category', kwargs={'slug': self.slug})
    
    @property
    def level(self):
        """Уровень вложенности категории с защитой от рекурсии"""
        if not self.parent:
            return 0
        
        # Защита от циклов - максимум 5 уровней
        visited = set()
        current = self
        level = 0
        
        while current.parent and current.id not in visited:
            visited.add(current.id)
            current = current.parent
            level += 1
            if level > 5:  # Максимум 5 уровней
                break
                
        return level


class SubCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    slug = models.SlugField(verbose_name='URL')
    parent = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories', verbose_name='Родительская категория')
    description = models.TextField(blank=True, verbose_name='Описание')
    image = models.ImageField(upload_to='subcategories/', blank=True, verbose_name='Изображение')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок сортировки')
    
    class Meta:
        verbose_name = 'Подкатегория'
        verbose_name_plural = 'Подкатегории'
        ordering = ['parent', 'order', 'name']
        unique_together = ('parent', 'slug')
    
    def __str__(self):
        return f"{self.parent.name} → {self.name}"
    
    def get_absolute_url(self):
        return reverse('shop:subcategory', kwargs={'category_slug': self.parent.slug, 'slug': self.slug})


class Brand(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    slug = models.SlugField(unique=True, verbose_name='URL')
    description = models.TextField(blank=True, verbose_name='Описание')
    logo = models.ImageField(upload_to='brands/', blank=True, verbose_name='Логотип')
    
    class Meta:
        verbose_name = 'Бренд'
        verbose_name_plural = 'Бренды'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Product(models.Model):
    tmp_id = models.CharField(max_length=100, blank=True, verbose_name='ID в 1С', db_index=True)
    name = models.CharField(max_length=200, verbose_name='Название')
    slug = models.SlugField(unique=True, verbose_name='URL')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='Категория')
    # Убираем subcategory - теперь category может быть дочерней категорией
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, verbose_name='Бренд')
    code = models.CharField(max_length=50, verbose_name='Код товара')
    catalog_number = models.CharField(max_length=50, verbose_name='Каталожный номер')
    cross_number = models.CharField(max_length=100, blank=True, verbose_name='Кросс-код товара')
    artikyl_number = models.CharField(max_length=100, blank=True, verbose_name='Дополнительный номер товара')
    description = models.TextField(blank=True, verbose_name='Описание')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    old_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Старая цена')
    applicability = models.TextField(blank=True, verbose_name='Применяемость')
    in_stock = models.BooleanField(default=True, verbose_name='В наличии')
    is_featured = models.BooleanField(default=False, verbose_name='Популярный товар')
    is_new = models.BooleanField(default=False, verbose_name='Новый товар')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    
    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('shop:product', kwargs={'slug': self.slug})
    
    @property
    def discount_percent(self):
        if self.old_price and self.old_price > self.price:
            return int(((self.old_price - self.price) / self.old_price) * 100)
        return 0
    
    @property
    def main_image_path(self):
        """Возвращает путь к главному изображению по структуре section_id/tmp_id"""
        if self.category and self.tmp_id:
            # Получаем SECTION_ID из родительской категории или самой категории
            root_category = self.category
            while root_category.parent:
                root_category = root_category.parent
            
            # SECTION_ID теперь хранится прямо в slug без префикса
            section_id = root_category.slug
            return f'{section_id}/{self.tmp_id}.jpg'
        return None
    
    @property  
    def has_main_image(self):
        """Проверяет существование главного изображения"""
        if self.main_image_path:
            import os
            from django.conf import settings
            
            # Проверяем существование файла
            full_path = os.path.join(settings.BASE_DIR, 'images', self.main_image_path)
            return os.path.exists(full_path)
        return False
    
    @property
    def main_image_url(self):
        """Возвращает URL для изображения"""
        if self.main_image_path:
            return f'/images/{self.main_image_path}'
        return None


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name='Товар')
    image = models.ImageField(upload_to='products/', verbose_name='Изображение')
    is_main = models.BooleanField(default=False, verbose_name='Главное изображение')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    
    class Meta:
        verbose_name = 'Изображение товара'
        verbose_name_plural = 'Изображения товаров'
        ordering = ['order']
    
    def __str__(self):
        return f"{self.product.name} - {self.image.name}"


class ProductAnalog(models.Model):
    """Модель для хранения аналогов товаров"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='analogs', verbose_name='Основной товар')
    analog_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='analog_for', verbose_name='Аналог')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    
    class Meta:
        verbose_name = 'Аналог товара'
        verbose_name_plural = 'Аналоги товаров'
        unique_together = ('product', 'analog_product')
    
    def __str__(self):
        return f"{self.product.name} -> {self.analog_product.name}"


class OeKod(models.Model):
    """Модель для хранения аналогов товаров (номера OE)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='oe_analogs', verbose_name='Товар')
    oe_kod = models.CharField(max_length=100, verbose_name='Номер аналога OE', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    
    class Meta:
        verbose_name = 'Аналог OE'
        verbose_name_plural = 'Аналоги OE'
        unique_together = ('product', 'oe_kod')
        indexes = [
            models.Index(fields=['oe_kod']),
        ]
    
    def __str__(self):
        return f"{self.product.name} -> {self.oe_kod}"
    
    @classmethod
    def is_number_search(cls, search_term):
        """Определяет является ли поисковый запрос номером детали"""
        # Удаляем пробелы
        term = search_term.strip()
        # Считаем номером если содержит цифры и не более 20% букв от общей длины
        if len(term) < 3:
            return False
        
        digit_count = sum(1 for c in term if c.isdigit())
        alpha_count = sum(1 for c in term if c.isalpha())
        special_count = sum(1 for c in term if c in '-._/')
        
        # Если есть цифры и общая длина не слишком большая
        if digit_count > 0 and len(term) <= 50:
            # Если много букв относительно цифр, скорее всего это название
            if alpha_count > digit_count * 2:
                return False
            return True
        return False


class ImportFile(models.Model):
    """Модель для загрузки CSV файлов импорта"""
    file = models.FileField(upload_to='imports/', verbose_name='CSV файл')
    original_filename = models.CharField(max_length=255, verbose_name='Исходное имя файла')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')
    processed = models.BooleanField(default=False, verbose_name='Обработан')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата обработки')
    
    # Прогресс импорта
    status = models.CharField(max_length=50, default='pending', verbose_name='Статус',
                             choices=[
                                 ('pending', 'Ожидает'),
                                 ('processing', 'Обрабатывается'),
                                 ('completed', 'Завершен'),
                                 ('failed', 'Ошибка'),
                                 ('cancelled', 'Отменен'),
                             ])
    current_row = models.IntegerField(default=0, verbose_name='Текущая строка')
    total_rows = models.IntegerField(default=0, verbose_name='Всего строк')
    processed_rows = models.IntegerField(default=0, verbose_name='Обработано строк')
    created_products = models.IntegerField(default=0, verbose_name='Создано товаров')
    updated_products = models.IntegerField(default=0, verbose_name='Обновлено товаров')
    error_count = models.IntegerField(default=0, verbose_name='Количество ошибок')
    error_log = models.TextField(blank=True, verbose_name='Лог ошибок')
    
    # Поле для отмены импорта
    cancelled = models.BooleanField(default=False, verbose_name='Отменен')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата отмены')
    
    # Прогресс в процентах
    @property
    def progress_percent(self):
        if self.total_rows == 0:
            return 0
        try:
            progress = int((self.current_row / self.total_rows) * 100)
            return min(100, max(0, progress))  # Ограничиваем от 0 до 100
        except (ValueError, TypeError, ZeroDivisionError):
            return 0
    
    # Скорость обработки
    @property
    def processing_speed(self):
        if not self.processed_at or self.status != 'processing':
            return 0
        try:
            from django.utils import timezone
            elapsed = (timezone.now() - self.uploaded_at).total_seconds()
            if elapsed > 0:
                return int(self.current_row / elapsed)
            return 0
        except (ValueError, TypeError, ZeroDivisionError):
            return 0
    
    # Можно ли отменить импорт
    @property
    def can_cancel(self):
        return self.status in ['pending', 'processing'] and not self.cancelled
    
    # Можно ли запустить импорт
    @property
    def can_start(self):
        return self.status == 'pending' and not self.processed and not self.cancelled
    
    class Meta:
        verbose_name = 'Импорт файл'
        verbose_name_plural = 'Импорт файлы'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.original_filename} ({self.uploaded_at})"
