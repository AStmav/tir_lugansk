from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView
from django.db.models import Q
from django.db import models
from .models import Product, Category, Brand


class CatalogView(ListView):
    model = Product
    template_name = 'catalog.html'
    context_object_name = 'products'
    paginate_by = 12
    
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
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(catalog_number__icontains=search) |
                Q(brand__name__icontains=search)
            )
        
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
        context['categories'] = Category.objects.all()
        context['brands'] = Brand.objects.all()
        
        # Выбранные фильтры для template
        context['selected_categories'] = self.request.GET.getlist('category')
        context['selected_brands'] = self.request.GET.getlist('brand')
        
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
