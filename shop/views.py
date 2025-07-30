from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView
from django.db.models import Q
from django.db import models
from .models import Product, Category, Brand, ProductAnalog


class CatalogView(ListView):
    model = Product
    template_name = 'catalog.html'
    context_object_name = 'products'
    paginate_by = 100
    
    def get_queryset(self):
        queryset = Product.objects.filter(in_stock=True)
        
        # Фильтр по категории (множественный выбор)
        category_slugs = self.request.GET.getlist('category')
        if category_slugs:
            queryset = queryset.filter(category__slug__in=category_slugs)
        
        # Фильтр по бренду (множественный выбор)
        brand_slugs = self.request.GET.getlist('brand')
        if brand_slugs:
            queryset = queryset.filter(brand__slug__in=brand_slugs)
        
        # Фильтр по цене
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        
        # Поиск
        search = self.request.GET.get('search')
        if search:
            # Основной поиск по товарам
            main_search = Q(name__icontains=search) | \
                         Q(code__icontains=search) | \
                         Q(catalog_number__icontains=search) | \
                         Q(brand__name__icontains=search)
            
            # Поиск товаров, которые являются аналогами найденных товаров
            analog_products = ProductAnalog.objects.filter(
                Q(product__name__icontains=search) |
                Q(product__code__icontains=search) |
                Q(product__catalog_number__icontains=search) |
                Q(product__brand__name__icontains=search)
            ).values_list('analog_product_id', flat=True)
            
            # Поиск товаров, для которых есть аналоги, найденные по поиску
            products_with_analogs = ProductAnalog.objects.filter(
                Q(analog_product__name__icontains=search) |
                Q(analog_product__code__icontains=search) |
                Q(analog_product__catalog_number__icontains=search) |
                Q(analog_product__brand__name__icontains=search)
            ).values_list('product_id', flat=True)
            
            # Объединяем все результаты поиска
            queryset = queryset.filter(
                main_search |
                Q(id__in=analog_products) |
                Q(id__in=products_with_analogs)
            ).distinct()
        
        # Сортировка
        sort = self.request.GET.get('sort', 'newest')
        if sort == 'price_asc':
            queryset = queryset.order_by('price')
        elif sort == 'price_desc':
            queryset = queryset.order_by('-price')
        elif sort == 'name':
            queryset = queryset.order_by('name')
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Основные категории (без родителя)
        context['main_categories'] = Category.objects.filter(parent=None, is_active=True).order_by('order', 'name')
        
        # Все категории для фильтра
        context['categories'] = Category.objects.filter(is_active=True).order_by('order', 'name')
        context['brands'] = Brand.objects.all()
        
        # Выбранные фильтры для template
        context['selected_categories'] = self.request.GET.getlist('category')
        context['selected_brands'] = self.request.GET.getlist('brand')
        
        # Поисковый запрос
        context['search_query'] = self.request.GET.get('search', '')
        
        # Минимальная и максимальная цена для фильтра
        if context['products']:
            context['min_price'] = context['products'].aggregate(min_price=models.Min('price'))['min_price']
            context['max_price'] = context['products'].aggregate(max_price=models.Max('price'))['max_price']
        
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
