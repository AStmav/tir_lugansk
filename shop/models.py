from django.db import models
from django.urls import reverse


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
        if self.category and self.code:
            # Получаем SECTION_ID из родительской категории или самой категории
            root_category = self.category
            while root_category.parent:
                root_category = root_category.parent
            
            # Извлекаем SECTION_ID из slug основной категории
            section_id = root_category.slug.replace('category-', '')
            return f'{section_id}/{self.code}.jpg'
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
