from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView
from django.db.models import Q
from django.db import models
from .models import Product, Category, Brand, OeKod
import logging

# Настройка логирования
logger = logging.getLogger(__name__)


class CatalogView(ListView):
    model = Product
    template_name = 'catalog.html'
    context_object_name = 'products'
    paginate_by = 100
    
    def get_queryset(self):
        # Начинаем с базового queryset всех товаров в наличии
        base_queryset = Product.objects.filter(in_stock=True)
        
        # Логируем базовый queryset
        logger.info(f"Базовый queryset: {base_queryset.count()} товаров")
        
        # Поиск согласно ТЗ (приоритет поиска выше фильтров)
        search = self.request.GET.get('search')
        if search:
            search = search.strip()
            logger.info(f"Поисковый запрос: '{search}'")
            
            # Определяем является ли запрос поиском по номеру
            if OeKod.is_number_search(search):
                logger.info(f"Поиск по номеру: '{search}'")
                
                # ПОИСК ПО НОМЕРУ - ищем по ВСЕМ товарам независимо от фильтров
                number_search_query = (
                    Q(catalog_number__istartswith=search) |  # PROPERTY_TMC_NUMBER
                    Q(artikyl_number__istartswith=search) |  # PROPERTY_ARTIKYL_NUMBER
                    Q(cross_number__istartswith=search)      # PROPERTY_CROSS_NUMBER
                )
                
                # Поиск в таблице аналогов OE
                oe_products = Product.objects.filter(
                    oe_analogs__oe_kod__istartswith=search
                ).distinct()
                
                logger.info(f"Найдено товаров по номеру: {Product.objects.filter(number_search_query).count()}")
                logger.info(f"Найдено товаров по OE аналогам: {oe_products.count()}")
                
                # Находим товары, соответствующие поиску по номеру
                found_products = Product.objects.filter(number_search_query).distinct()
                
                # Объединяем результаты
                if oe_products.exists():
                    found_products = found_products.union(oe_products).distinct()
                
                if found_products.exists():
                    logger.info(f"Всего найдено товаров по номеру: {found_products.count()}")
                    
                    # Этап 2: Собираем все номера найденных товаров для поиска связанных
                    related_numbers = set()
                    
                    for product in found_products:
                        # Добавляем номера товара
                        if product.catalog_number:  # PROPERTY_TMC_NUMBER
                            related_numbers.add(product.catalog_number)
                        if product.artikyl_number:  # PROPERTY_ARTIKYL_NUMBER
                            related_numbers.add(product.artikyl_number)
                        if product.cross_number:    # PROPERTY_CROSS_NUMBER
                            related_numbers.add(product.cross_number)
                    
                    logger.info(f"Связанных номеров найдено: {len(related_numbers)}")
                    
                    # Этап 3: Находим все товары с точным совпадением этих номеров
                    if related_numbers:
                        analog_query = Q()
                        for number in related_numbers:
                            analog_query |= (
                                Q(catalog_number__exact=number) |  # PROPERTY_TMC_NUMBER
                                Q(artikyl_number__exact=number) |  # PROPERTY_ARTIKYL_NUMBER  
                                Q(cross_number__exact=number)      # PROPERTY_CROSS_NUMBER
                            )
                        
                        # Финальный результат: объединяем найденные товары и их аналоги
                        queryset = base_queryset.filter(analog_query).distinct()
                        logger.info(f"Финальный результат поиска по номеру: {queryset.count()} товаров")
                    else:
                        queryset = base_queryset.filter(pk__in=[p.pk for p in found_products])
                        logger.info(f"Результат поиска по номеру (без аналогов): {queryset.count()} товаров")
                else:
                    # Если по номеру ничего не найдено, возвращаем пустой результат
                    logger.warning(f"По номеру '{search}' ничего не найдено")
                    queryset = Product.objects.none()
            else:
                logger.info(f"Поиск по тексту: '{search}'")
                
                # ПОИСК ПО НАЗВАНИЮ И БРЕНДУ - ищем по ВСЕМ товарам независимо от фильтров
                text_search_query = (
                    Q(name__icontains=search) |
                    Q(brand__name__icontains=search) |
                    Q(description__icontains=search) |
                    Q(applicability__icontains=search)
                )
                
                queryset = base_queryset.filter(text_search_query)
                logger.info(f"Результат поиска по тексту: {queryset.count()} товаров")
        else:
            # Если поиска нет, применяем фильтры к базовому queryset
            queryset = base_queryset
            logger.info("Поисковый запрос отсутствует, применяем только фильтры")
        
        # Применяем фильтры только если НЕ было поиска или поиск вернул результаты
        if not search or (search and queryset.exists()):
            # Фильтр по категории (множественный выбор)
            category_slugs = self.request.GET.getlist('category')
            if category_slugs:
                logger.info(f"Применяем фильтр по категориям: {category_slugs}")
                queryset = queryset.filter(category__slug__in=category_slugs)
                logger.info(f"После фильтра по категориям: {queryset.count()} товаров")
            
            # Фильтр по бренду (множественный выбор)
            brand_slugs = self.request.GET.getlist('brand')
            if brand_slugs:
                logger.info(f"Применяем фильтр по брендам: {brand_slugs}")
                queryset = queryset.filter(brand__slug__in=brand_slugs)
                logger.info(f"После фильтра по брендам: {queryset.count()} товаров")
            
            # Фильтр по цене
            min_price = self.request.GET.get('min_price')
            max_price = self.request.GET.get('max_price')
            if min_price:
                logger.info(f"Применяем фильтр по минимальной цене: {min_price}")
                queryset = queryset.filter(price__gte=min_price)
                logger.info(f"После фильтра по минимальной цене: {queryset.count()} товаров")
            if max_price:
                logger.info(f"Применяем фильтр по максимальной цене: {max_price}")
                queryset = queryset.filter(price__lte=max_price)
                logger.info(f"После фильтра по максимальной цене: {queryset.count()} товаров")
        
        # Сортировка
        sort = self.request.GET.get('sort', 'newest')
        if sort == 'price_asc':
            queryset = queryset.order_by('price')
            logger.info("Сортировка по возрастанию цены")
        elif sort == 'price_desc':
            queryset = queryset.order_by('-price')
            logger.info("Сортировка по убыванию цены")
        elif sort == 'name':
            queryset = queryset.order_by('name')
            logger.info("Сортировка по названию")
        else:
            queryset = queryset.order_by('-created_at')
            logger.info("Сортировка по дате создания (новые сначала)")
        
        logger.info(f"Финальный результат: {queryset.count()} товаров")
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Логируем контекст
        logger.info(f"Формируем контекст для страницы каталога")
        
        # Основные категории (без родителя)
        context['main_categories'] = Category.objects.filter(parent=None, is_active=True).order_by('order', 'name')
        logger.info(f"Основных категорий: {context['main_categories'].count()}")
        
        # Все категории для фильтра
        context['categories'] = Category.objects.filter(is_active=True).order_by('order', 'name')
        context['brands'] = Brand.objects.all()
        logger.info(f"Всего категорий для фильтра: {context['categories'].count()}")
        logger.info(f"Всего брендов для фильтра: {context['brands'].count()}")
        
        # Выбранные фильтры для template
        context['selected_categories'] = self.request.GET.getlist('category')
        context['selected_brands'] = self.request.GET.getlist('brand')
        logger.info(f"Выбранные категории: {context['selected_categories']}")
        logger.info(f"Выбранные бренды: {context['selected_brands']}")
        
        # Поисковый запрос
        context['search_query'] = self.request.GET.get('search', '')
        if context['search_query']:
            logger.info(f"Поисковый запрос в контексте: '{context['search_query']}'")
        
        # Минимальная и максимальная цена для фильтра
        if context['products']:
            context['min_price'] = context['products'].aggregate(min_price=models.Min('price'))['min_price']
            context['max_price'] = context['products'].aggregate(max_price=models.Max('price'))['max_price']
            logger.info(f"Диапазон цен: {context['min_price']} - {context['max_price']}")
        
        logger.info(f"Контекст сформирован, товаров в контексте: {context['products'].count() if context['products'] else 0}")
        return context


class ProductView(DetailView):
    model = Product
    template_name = 'product.html'
    context_object_name = 'product'
    slug_url_kwarg = 'slug'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Похожие товары (из той же категории, исключая текущий товар)
        related_products = Product.objects.filter(
            category=self.object.category,
            in_stock=True
        ).exclude(id=self.object.id)[:6]
        
        context['related_products'] = related_products
        
        return context
