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
    
    # SEO поля
    meta_title = models.CharField(max_length=255, blank=True, verbose_name='SEO заголовок')
    meta_description = models.TextField(max_length=320, blank=True, verbose_name='SEO описание')
    meta_keywords = models.CharField(max_length=255, blank=True, verbose_name='SEO ключевые слова')
    
    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['order', 'name']
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name
    
    def get_absolute_url(self):
        """Возвращает URL каталога с фильтром по категории"""
        from django.urls import reverse
        return f"{reverse('shop:catalog')}?category={self.id}"
    
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
        """Возвращает URL каталога с фильтром по подкатегории"""
        from django.urls import reverse
        return f"{reverse('shop:catalog')}?category={self.parent.id}"


class Brand(models.Model):
    code = models.CharField(max_length=100, unique=True, null=True, blank=True, verbose_name='Код')
    name = models.CharField(max_length=100, verbose_name='Название')
    slug = models.SlugField(unique=True, verbose_name='URL')
    description = models.TextField(blank=True, verbose_name='Описание')
    logo = models.ImageField(upload_to='brands/', blank=True, verbose_name='Логотип')
    
    # SEO поля
    meta_title = models.CharField(max_length=255, blank=True, verbose_name='SEO заголовок')
    meta_description = models.TextField(max_length=320, blank=True, verbose_name='SEO описание')
    meta_keywords = models.CharField(max_length=255, blank=True, verbose_name='SEO ключевые слова')
    
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
    
    # НОВЫЕ ПОЛЯ: Очищенные номера для быстрого поиска
    catalog_number_clean = models.CharField(
        max_length=50, 
        blank=True, 
        db_index=True,
        verbose_name='Каталожный номер (очищенный)',
        help_text='Автоматически генерируется без пробелов и знаков препинания'
    )
    artikyl_number_clean = models.CharField(
        max_length=100, 
        blank=True, 
        db_index=True,
        verbose_name='Дополнительный номер (очищенный)',
        help_text='Автоматически генерируется без пробелов и знаков препинания'
    )
    
    description = models.TextField(blank=True, verbose_name='Описание')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    old_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Старая цена')
    applicability = models.TextField(blank=True, verbose_name='Применяемость')
    in_stock = models.BooleanField(default=True, verbose_name='В наличии')
    is_featured = models.BooleanField(default=False, verbose_name='Популярный товар')
    is_new = models.BooleanField(default=False, verbose_name='Новый товар')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    
    # SEO поля
    meta_title = models.CharField(max_length=255, blank=True, verbose_name='SEO заголовок')
    meta_description = models.TextField(max_length=320, blank=True, verbose_name='SEO описание')
    meta_keywords = models.CharField(max_length=255, blank=True, verbose_name='SEO ключевые слова')
    
    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['catalog_number_clean']),
            models.Index(fields=['artikyl_number_clean']),
            models.Index(fields=['tmp_id']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Автоматически очищаем номера и генерируем SEO теги при сохранении"""
        self.catalog_number_clean = self.clean_number(self.catalog_number)
        self.artikyl_number_clean = self.clean_number(self.artikyl_number)
        
        # Автогенерация SEO тегов если они пустые
        if not self.meta_title:
            self.meta_title = self.generate_meta_title()
        if not self.meta_description:
            self.meta_description = self.generate_meta_description()
        if not self.meta_keywords:
            self.meta_keywords = self.generate_meta_keywords()
            
        super().save(*args, **kwargs)
    
    @staticmethod
    def clean_number(number):
        """
        Удаляет все символы кроме букв и цифр.
        
        ИСПРАВЛЕНО: Добавлена поддержка кириллицы для OE номеров
        
        Примеры:
        '6.45004' → '645004'
        '5 000 289 804' → '5000289804'
        'ABC-123.456' → 'abc123456'
        'Яблоко M16/8' → 'яблоком168'
        """
        if not number:
            return ''
        # Удаляем все кроме букв (латиница + кириллица) и цифр
        cleaned = re.sub(r'[^a-zA-Zа-яА-ЯёЁ0-9]', '', str(number))
        # Приводим к нижнему регистру
        return cleaned.lower()
    
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
    
    def generate_meta_title(self):
        """Генерирует SEO заголовок для товара"""
        brand_name = self.brand.name if self.brand else ''
        category_name = self.category.name if self.category else ''
        parts = [part for part in [self.name, brand_name, self.catalog_number] if part]
        title = ' '.join(parts)
        if category_name:
            title += f' - {category_name}'
        title += ' | Купить в Луганске'
        return title[:255]  # Ограничиваем длину
    
    def generate_meta_description(self):
        """Генерирует SEO описание для товара"""
        brand_name = self.brand.name if self.brand else 'качественный производитель'
        category_name = self.category.name if self.category else 'автозапчасти'
        
        desc = f'Купить {self.name} {brand_name} (арт. {self.catalog_number}) '
        desc += f'в Луганске. {category_name}. '
        
        if self.price:
            desc += f'Цена: {self.price} руб. '
        
        if self.in_stock:
            desc += 'В наличии. '
        
        if self.applicability:
            # Берем первые 50 символов применяемости
            applicability_short = self.applicability[:50]
            desc += f'Применяемость: {applicability_short}... '
        
        desc += 'Доставка по Луганску и ЛНР.'
        
        return desc[:320]  # Ограничиваем длину для SEO
    
    def generate_meta_keywords(self):
        """Генерирует SEO ключевые слова для товара"""
        keywords = []
        
        if self.name:
            keywords.append(self.name.lower())
        
        if self.brand and self.brand.name:
            keywords.append(self.brand.name.lower())
            keywords.append(f'{self.brand.name.lower()} {self.name.lower()}')
        
        if self.catalog_number:
            keywords.append(self.catalog_number.lower())
            keywords.append(f'артикул {self.catalog_number.lower()}')
        
        if self.category and self.category.name:
            keywords.append(self.category.name.lower())
        
        # Добавляем общие ключевые слова
        keywords.extend(['автозапчасти', 'луганск', 'купить автозапчасти'])
        
        return ', '.join(keywords[:15])  # Ограничиваем количество ключевых слов
    
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
    
    @property
    def url(self):
        """
        Возвращает URL изображения.
        Поддерживает как пути в media/, так и прямые пути images/
        """
        if self.image:
            # Преобразуем в строку
            image_str = str(self.image)
            
            # Если путь начинается с images/ - возвращаем как есть
            if image_str.startswith('images/'):
                return f'/{image_str}'
            
            # Если это путь через ImageField (в MEDIA_ROOT)
            if hasattr(self.image, 'url'):
                try:
                    return self.image.url
                except (ValueError, AttributeError):
                    pass
            
            # Иначе добавляем MEDIA_URL
            if image_str:
                return f'/media/{image_str}'
        
        return '/static/img/zaglushka.jpg'  # Заглушка если нет изображения


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
    """
    Модель для хранения аналогов товаров (номера OE)
    Структура из файла oe_nomer.DBF:
    - ID_OE: Уникальный порядковый номер аналога (уникальный идентификатор)
    - NAME: Каталожный номер аналога
    - Name_STR: Каталожный номер без символов (очищенный)
    - ID_BREND: ID производителя
    - ID_TOVAR: ID товара-владельца
    
    ЛОГИКА СВЯЗЕЙ:
    - ID_OE - уникальный идентификатор каждого аналога
    - У одного товара (ID_TOVAR) может быть множество аналогов (ID_OE)
    - Связь: Product (1) → OeKod (много) через ForeignKey
    """
    # ID аналога из 1С (уникальный порядковый номер аналога)
    id_oe = models.CharField(
        max_length=50, 
        unique=True,
        db_index=True,
        verbose_name='ID аналога 1С',
        help_text='Уникальный порядковый номер аналога из файла oe_nomer.DBF. Каждый аналог имеет уникальный ID_OE.'
    )
    
    # Связь с товаром (владелец аналога)
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='oe_analogs', 
        verbose_name='Товар',
        null=True,
        blank=True,
        help_text='Товар-владелец аналога. Может быть NULL если товар ещё не импортирован.'
    )
    
    # Связь с брендом аналога
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oe_analogs',
        verbose_name='Бренд аналога'
    )
    
    # Каталожный номер аналога (NAME из файла)
    oe_kod = models.CharField(
        max_length=100, 
        db_index=True,
        verbose_name='Номер аналога OE'
    )
    
    # Очищенный каталожный номер (Name_STR из файла)
    oe_kod_clean = models.CharField(
        max_length=100,
        db_index=True,
        blank=True,
        verbose_name='Номер аналога OE (очищенный)',
        help_text='Номер без пробелов и знаков препинания для быстрого поиска'
    )
    
    # ID товара из файла (для отладки и связи)
    id_tovar = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        verbose_name='ID товара из 1С',
        help_text='ID_TOVAR из файла oe_nomer.DBF. Используется для связи с товаром и составного уникального индекса.'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    
    class Meta:
        verbose_name = 'Аналог OE'
        verbose_name_plural = 'Аналоги OE'
        # ID_OE - уникальный идентификатор аналога
        # Один товар (ID_TOVAR) может иметь множество аналогов (ID_OE)
        # Связь: Product (1) → OeKod (много) через ForeignKey
        indexes = [
            models.Index(fields=['oe_kod_clean']),
            models.Index(fields=['oe_kod']),
            models.Index(fields=['id_oe']),
            models.Index(fields=['id_tovar']),
        ]
    
    def __str__(self):
        product_name = self.product.name if self.product else f"[Товар: {self.id_tovar}]"
        if self.brand:
            return f"{product_name} → {self.brand.name} {self.oe_kod}"
        return f"{product_name} → {self.oe_kod}"
    
    @staticmethod
    def clean_number(number):
        """
        Удаляет все символы кроме букв и цифр для поиска.
        
        ИСПРАВЛЕНО: Добавлена поддержка кириллицы (а-яА-Я) для OE номеров
        Пример: "Яблоко M16/8" → "ЯблокоM168" → "яблоком168" (lowercase)
        """
        if not number:
            return ''
        # Удаляем все кроме букв (латиница + кириллица) и цифр
        # ИСПРАВЛЕНО: Было [^a-zA-Z0-9], добавлено а-яА-ЯёЁ
        cleaned = re.sub(r'[^a-zA-Zа-яА-ЯёЁ0-9]', '', str(number))
        # Приводим к нижнему регистру для единообразия
        return cleaned.lower()
    
    @classmethod
    def is_number_search(cls, search_term):
        """
        Определяет является ли поисковый запрос номером детали.
        
        ИСПРАВЛЕНО: Ослаблено условие для OE номеров с буквами (например, "яблоком168")
        """
        # Удаляем пробелы
        term = search_term.strip()
        
        if len(term) < 3:
            return False
        
        digit_count = sum(1 for c in term if c.isdigit())
        alpha_count = sum(1 for c in term if c.isalpha())
        special_count = sum(1 for c in term if c in '-._/')
        
        # 1. Специальная логика для TMP_ID (обычно только цифры, например 000179920)
        if term.isdigit() and len(term) >= 6:
            return True
        
        # 2. Если >= 3 цифры и длина разумная - считаем номером
        #    ИСПРАВЛЕНО: Было digit_count > 0, теперь >= 3
        #    Покрывает OE номера типа "яблоком168", "abc123", "5000289804"
        if digit_count >= 3 and len(term) <= 50:
            return True
        
        # 3. Для коротких номеров с 1-2 цифрами - проверяем соотношение
        #    (например, "A1", "B12" - скорее всего номера)
        if digit_count > 0 and len(term) <= 50:
            # ИСПРАВЛЕНО: Было alpha_count > digit_count * 2
            # Теперь: alpha_count > digit_count * 5 (более мягкое условие)
            # Это отсечет только явные названия типа "масло моторное 5w40"
            if alpha_count > digit_count * 5:
                return False
            return True
        
        return False


class ImportFile(models.Model):
    """Модель для загрузки CSV и DBF файлов импорта"""
    file = models.FileField(upload_to='imports/', verbose_name='Файл импорта (CSV/DBF)')
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
    
    # ==================== НОВЫЕ ПОЛЯ ДЛЯ ВАЛИДАЦИИ ====================
    # Тип файла (бренды, товары, аналоги)
    file_type = models.CharField(
        max_length=20,
        choices=[
            ('brands', 'Бренды (ID_BRENB, NAME)'),
            ('products', 'Товары (TMP_ID, PROPERTY_P, PROPERTY_T)'),
            ('analogs', 'OE Аналоги (ID_OE, ID_TOVAR, ID_BRENB)'),
        ],
        blank=True,
        null=True,
        verbose_name='Тип файла',
        help_text='Выберите тип импортируемых данных'
    )
    
    # Статус валидации
    validation_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Ожидает проверки'),
            ('valid', 'Структура корректна'),
            ('invalid', 'Структура не соответствует'),
            ('warning', 'Есть предупреждения'),
        ],
        default='pending',
        verbose_name='Статус валидации'
    )
    
    # Сообщение валидации
    validation_message = models.TextField(
        blank=True,
        verbose_name='Результат проверки',
        help_text='Детали валидации файла'
    )
    
    # Обнаруженные поля (JSON)
    detected_fields = models.JSONField(
        blank=True,
        null=True,
        verbose_name='Обнаруженные поля',
        help_text='Список полей найденных в DBF'
    )
    
    # Предложенный тип
    suggested_type = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Предложенный тип',
        help_text='Автоматически определенный тип файла'
    )
    
    # Режим обработки дубликатов (НОВОЕ ПОЛЕ)
    update_mode = models.CharField(
        max_length=20,
        choices=[
            ('update', '🔄 Обновить существующие'),
            ('skip', '⏭️ Пропустить существующие'),
            ('create_only', '🔸 Создать дубликаты (старый режим)'),
        ],
        default='update',
        verbose_name='Режим обработки дубликатов',
        help_text='Что делать при повторном импорте существующих товаров?'
    )
    # ==================== КОНЕЦ НОВЫХ ПОЛЕЙ ====================
    
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
    
    @property
    def is_dbf_file(self):
        """Проверяет, является ли файл DBF файлом"""
        if self.original_filename:
            return self.original_filename.lower().endswith('.dbf')
        return False
    
    @property
    def is_csv_file(self):
        """Проверяет, является ли файл CSV файлом"""
        if self.original_filename:
            return self.original_filename.lower().endswith('.csv')
        return False
    
    @property
    def file_type_display(self):
        """Возвращает тип файла для отображения"""
        if self.is_dbf_file:
            return 'DBF'
        elif self.is_csv_file:
            return 'CSV'
        else:
            return 'Неизвестный'
