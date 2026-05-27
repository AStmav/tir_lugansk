from collections import defaultdict

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponsePermanentRedirect
from django.urls import reverse
from django.views.generic import TemplateView, ListView, DetailView
from django.db.models import Q, Prefetch
from django.db import models
from django.core.cache import cache
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Product, Category, Brand, OeKod
from .brand_urls import build_catalog_brand_redirect
from .category_urls import build_catalog_category_redirect, category_canonical_url
from .seo import ProductSEOMixin, BrandSEOMixin, CategorySEOMixin, SEOMixin
import logging
import re
import hashlib

# Настройка логирования
logger = logging.getLogger(__name__)


def normalize_latin_to_cyrillic(text):
    """
    Нормализует латинские буквы, визуально похожие на кириллицу, в кириллицу.
    Решает проблему когда пользователь вводит "Яблоко M16/8" (Latin M),
    а в базе записано "Яблоко М16/8" (Cyrillic М).
    
    Пример:
        "Apple M16" → "Apple М16" (M → М)
        "KOMETA" → "КОМЕТА" (K,O,M,E,T,A → К,О,М,Е,Т,А)
    """
    # Мапа похожих букв: Latin → Cyrillic
    latin_to_cyrillic_map = {
        # Заглавные
        'A': 'А', 'B': 'В', 'C': 'С', 'E': 'Е', 'H': 'Н',
        'K': 'К', 'M': 'М', 'O': 'О', 'P': 'Р', 'T': 'Т',
        'X': 'Х', 'Y': 'У',
        # Строчные
        'a': 'а', 'c': 'с', 'e': 'е', 'o': 'о', 'p': 'р',
        'x': 'х', 'y': 'у',
    }
    
    result = []
    for char in text:
        result.append(latin_to_cyrillic_map.get(char, char))
    return ''.join(result)


def _parse_search_mode(query):
    """
    Единая логика для подсказок и каталога: без % — только по началу (prefix),
    с % — и в середине (contains). Возвращает (строка_без_процента, разрешить_поиск_в_середине).
    """
    if not query:
        return query, False
    allow_contains = '%' in query
    stripped = query.replace('%', '').strip()
    return stripped, allow_contains


def _normalize_search_mode(value):
    mode = (value or '').strip().lower()
    return mode if mode in ('name', 'code') else 'code'


@require_GET
def search_autocomplete(request):
    """
    Асинхронные подсказки для поиска (autocomplete).
    GET-параметр q — строка запроса (минимум 2 символа).
    По номерам: по умолчанию только по началу; с % в запросе — и в середине.
    """
    q = (request.GET.get('q') or '').strip()
    search_mode = _normalize_search_mode(request.GET.get('search_mode'))
    if len(q) < 2:
        return JsonResponse({'suggestions': []})
    brand_slug = (request.GET.get('brand') or '').strip()
    cache_key = f'autocomplete:{q}:{search_mode}:{brand_slug or "-"}'
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse({'suggestions': cached})

    q_work, allow_contains = _parse_search_mode(q)
    q_normalized = normalize_latin_to_cyrillic(q_work)
    q_clean = Product.clean_number(q_work)
    q_clean_norm = Product.clean_number(q_normalized)
    suggestions = []
    seen_values = set()
    max_items = 10

    # Режим подсказок:
    # - name: только название;
    # - code: только кодовые поля.
    if search_mode == 'code':
        product_q = (
            Q(catalog_number_clean__istartswith=q_clean) |
            Q(catalog_number_clean__istartswith=q_clean_norm) |
            Q(artikyl_number_clean__istartswith=q_clean) |
            Q(artikyl_number_clean__istartswith=q_clean_norm) |
            Q(catalog_number__iexact=q_work) |
            Q(catalog_number__iexact=q_normalized) |
            Q(artikyl_number__iexact=q_work) |
            Q(artikyl_number__iexact=q_normalized) |
            Q(catalog_number_clean__iexact=q_clean) |
            Q(artikyl_number_clean__iexact=q_clean_norm)
        )
        if allow_contains:
            product_q |= (
                Q(catalog_number__icontains=q_normalized) |
                Q(catalog_number_clean__icontains=q_clean) |
                Q(artikyl_number__icontains=q_work) |
                Q(artikyl_number_clean__icontains=q_clean)
            )
    else:
        product_q = Q(name__icontains=q_normalized) | Q(applicability__icontains=q_normalized)
    products = Product.objects.filter(in_stock=True).filter(product_q)
    # Если передан бренд (напр. с каталога с выбранным фильтром) — ищем только в нём
    if brand_slug:
        products = products.filter(brand__slug=brand_slug)
    products = products.select_related('brand').distinct()[:max_items]
    for p in products:
        val = (p.catalog_number or p.artikyl_number or p.name or '').strip()
        if not val or val in seen_values:
            continue
        seen_values.add(val)
        brand_name = p.brand.name if p.brand else ''
        text = p.name
        if p.catalog_number:
            text += ' (' + p.catalog_number + ')'
        if brand_name:
            text += ' — ' + brand_name
        suggestions.append({'text': text[:80] + ('…' if len(text) > 80 else ''), 'value': val[:120]})
        if len(suggestions) >= max_items:
            break

    # Подсказки по брендам добавляем только в режиме поиска по названию
    if search_mode == 'name' and len(suggestions) < max_items:
        brands = (
            Brand.objects.filter(name__icontains=q_normalized)
            .distinct()[:max_items - len(suggestions)]
        )
        for b in brands:
            val = b.name.strip()
            if val and val not in seen_values:
                seen_values.add(val)
                suggestions.append({'text': 'Бренд: ' + b.name, 'value': val})
                if len(suggestions) >= max_items:
                    break

    cache.set(cache_key, suggestions, 90)
    return JsonResponse({'suggestions': suggestions})


def legacy_supplier_brand_redirect(request, brand_slug):
    """301 со старого /suppliers/<slug>/ на /shop/brand/<slug>/."""
    return HttpResponsePermanentRedirect(
        reverse('shop:brand', kwargs={'brand_slug': brand_slug})
    )


class CatalogView(BrandSEOMixin, CategorySEOMixin, ListView):
    """
    Каталог товаров с SEO оптимизацией.
    Категория: /shop/category/<slug>/, бренд: /shop/brand/<slug>/ (тот же шаблон и фильтры).
    """
    model = Product
    template_name = 'catalog.html'
    context_object_name = 'products'
    paginate_by = 100

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.category = None
        self.brand = None
        category_slug = kwargs.get('category_slug')
        if category_slug:
            self.category = get_object_or_404(
                Category,
                slug=category_slug,
                is_active=True,
            )
        brand_slug = kwargs.get('brand_slug')
        if brand_slug:
            self.brand = get_object_or_404(Brand, slug=brand_slug)

    def get(self, request, *args, **kwargs):
        if not kwargs.get('category_slug') and not kwargs.get('brand_slug'):
            redirect_url = build_catalog_category_redirect(request)
            if redirect_url:
                return HttpResponsePermanentRedirect(redirect_url)
            redirect_url = build_catalog_brand_redirect(request)
            if redirect_url:
                return HttpResponsePermanentRedirect(redirect_url)
        return super().get(request, *args, **kwargs)

    def _get_category_filter_values(self):
        """Список slug/id категорий для фильтрации и отображения чекбоксов."""
        if (self.request.GET.get('search') or '').strip():
            return self.request.GET.getlist('category')
        get_cats = self.request.GET.getlist('category')
        if get_cats:
            return get_cats
        if getattr(self, 'category', None):
            return [self.category.slug]
        return []

    def _get_brand_filter_values(self):
        """Список slug брендов для фильтрации и чекбоксов."""
        if (self.request.GET.get('search') or '').strip():
            return self.request.GET.getlist('brand')
        get_brands = self.request.GET.getlist('brand')
        if get_brands:
            return get_brands
        if getattr(self, 'brand', None):
            return [self.brand.slug]
        return []

    def _build_catalog_cache_key(self):
        """
        Кэшируем только листинг без search (иначе рискуем затронуть сложную логику found_analogs).
        Ключ строим из стабильного набора фильтров/сортировки.
        """
        if (self.request.GET.get('search') or '').strip():
            return None

        category_slugs = sorted(self._get_category_filter_values())
        brand_slugs = sorted(self._get_brand_filter_values())
        min_price = (self.request.GET.get('min_price') or '').strip()
        max_price = (self.request.GET.get('max_price') or '').strip()
        sort = (self.request.GET.get('sort') or 'newest').strip()

        # Для «чистого каталога без фильтров» кэш id не нужен — список может быть очень большой.
        if not (category_slugs or brand_slugs or min_price or max_price or sort != 'newest'):
            return None

        payload = f"cat={','.join(category_slugs)}|brand={','.join(brand_slugs)}|min={min_price}|max={max_price}|sort={sort}"
        digest = hashlib.sha1(payload.encode('utf-8')).hexdigest()
        return f"catalog:ids:{digest}"
    
    def get_queryset(self):
        """
        ОПТИМИЗИРОВАННЫЙ ПОИСК с использованием очищенных номеров
        - Использует catalog_number_clean, artikyl_number_clean для быстрого поиска
        - Использует oe_kod_clean для поиска по аналогам
        - Оптимизирует запросы с select_related и prefetch_related
        - Результат кешируется на время запроса (ListView может вызывать get_queryset несколько раз)
        """
        # Кеш на время одного запроса — избегаем повторного тяжёлого поиска при пагинации/count
        if getattr(self, '_queryset_cache', None) is not None:
            return self._queryset_cache

        # Этап 4 Redis: быстрый путь для фильтрованного каталога (без search)
        ids_cache_key = self._build_catalog_cache_key()
        if ids_cache_key:
            cached_ids = cache.get(ids_cache_key)
            if cached_ids:
                self._found_analogs = OeKod.objects.none()
                sort = (self.request.GET.get('sort') or 'newest').strip()
                self._queryset_cache = Product.objects.filter(id__in=cached_ids).select_related(
                    'category', 'brand'
                ).prefetch_related('images')
                if sort == 'price_asc':
                    self._queryset_cache = self._queryset_cache.order_by('price')
                elif sort == 'price_desc':
                    self._queryset_cache = self._queryset_cache.order_by('-price')
                elif sort == 'name':
                    self._queryset_cache = self._queryset_cache.order_by('name')
                else:
                    self._queryset_cache = self._queryset_cache.order_by('-created_at')
                logger.info("Каталог: использован Redis-кэш id для фильтрованного листинга")
                return self._queryset_cache

        # Инициализируем список найденных аналогов
        self._found_analogs = OeKod.objects.none()
        
        # Начинаем с базового queryset с оптимизацией.
        # Для каталога нам нужны brand/category и изображения карточек.
        # Тяжёлый prefetch oe_analogs убираем из базового пути: он не нужен для рендера карточек.
        base_queryset = Product.objects.filter(
            in_stock=True
        ).select_related(
            'category', 'brand'
        ).prefetch_related(
            'images'
        )
        
        # Не вызываем .count() в проде — лишний тяжёлый запрос (оптимизация)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Базовый queryset: {base_queryset.count()} товаров")
        
        # Поиск согласно ТЗ (приоритет поиска выше фильтров)
        search_is_number = False
        search_priority_raw = ''
        search_priority_clean = ''
        search_priority_clean_normalized = ''
        search_mode = _normalize_search_mode(self.request.GET.get('search_mode'))
        search = self.request.GET.get('search')
        if search:
            search = search.strip()
            # Без % — только по началу номера; с % — и в середине (как в подсказках)
            search, allow_contains = _parse_search_mode(search)
            logger.info(f"Поисковый запрос: '{search}' (поиск в середине: {allow_contains})")
            
            # Режим "по коду": ищем только по кодовым полям.
            # Режим "по названию": ищем только по текстовым полям.
            if search_mode == 'code':
                search_is_number = True
                logger.info(f"Поиск по номеру: '{search}'")
                
                # КРИТИЧНО: Очищаем поисковый запрос от символов
                search_clean = Product.clean_number(search)
                search_priority_raw = search
                search_priority_clean = search_clean
                logger.info(f"Очищенный запрос: '{search_clean}'")
                
                # ИСПРАВЛЕНИЕ: Создаем нормализованную версию (Latin → Cyrillic)
                # Для случаев типа "Яблоко M16/8" (Latin M) → "Яблоко М16/8" (Cyrillic М)
                search_normalized = normalize_latin_to_cyrillic(search)
                search_clean_normalized = Product.clean_number(search_normalized)
                search_priority_clean_normalized = search_clean_normalized
                
                # Проверяем нужна ли нормализация (избегаем дублирования условий)
                needs_normalization = (search_clean != search_clean_normalized)
                
                # Логируем обе версии для отладки
                if needs_normalization:
                    logger.info(f"Нормализованный запрос: '{search_clean_normalized}' (Latin→Cyrillic)")
                else:
                    logger.info(f"Нормализация не требуется (нет латиницы)")
                
                # Для коротких номеров: по умолчанию только точное; с % в запросе — и в середине
                if len(search_clean) < 4:
                    logger.info(f"Короткий номер, точное + {'содержит' if allow_contains else 'только по началу'}")
                    number_search_query = (
                        Q(code__iexact=search) |
                        Q(tmp_id__iexact=search) |
                        Q(catalog_number__iexact=search) |
                        Q(artikyl_number__iexact=search) |
                        Q(catalog_number_clean__iexact=search_clean) |
                        Q(artikyl_number_clean__iexact=search_clean)
                    )
                    if allow_contains:
                        number_search_query |= (
                            Q(catalog_number__icontains=search) |
                            Q(artikyl_number__icontains=search) |
                            Q(catalog_number_clean__icontains=search_clean) |
                            Q(artikyl_number_clean__icontains=search_clean)
                        )
                    if needs_normalization:
                        number_search_query |= (
                            Q(catalog_number__iexact=search_normalized) |
                            Q(artikyl_number__iexact=search_normalized) |
                            Q(catalog_number_clean__iexact=search_clean_normalized) |
                            Q(artikyl_number_clean__iexact=search_clean_normalized)
                        )
                        if allow_contains:
                            number_search_query |= (
                                Q(catalog_number__icontains=search_normalized) |
                                Q(artikyl_number__icontains=search_normalized) |
                                Q(catalog_number_clean__icontains=search_clean_normalized) |
                                Q(artikyl_number_clean__icontains=search_clean_normalized)
                            )
                    
                    oe_search_query = Q(oe_analogs__oe_kod_clean__iexact=search_clean)
                    if allow_contains:
                        oe_search_query |= Q(oe_analogs__oe_kod_clean__icontains=search_clean)
                    if needs_normalization:
                        oe_search_query |= Q(oe_analogs__oe_kod_clean__iexact=search_clean_normalized)
                        if allow_contains:
                            oe_search_query |= Q(oe_analogs__oe_kod_clean__icontains=search_clean_normalized)
                else:
                    # Длинный номер: по умолчанию только точное + начинается с; с % — и в середине
                    logger.info(f"Длинный номер, точное + по началу + {'содержит' if allow_contains else 'без поиска в середине'}")
                    number_search_query = (
                        Q(code__iexact=search) |
                        Q(tmp_id__iexact=search) |
                        Q(catalog_number__iexact=search) |
                        Q(artikyl_number__iexact=search) |
                        Q(cross_number__iexact=search) |
                        Q(catalog_number_clean__iexact=search_clean) |
                        Q(artikyl_number_clean__iexact=search_clean) |
                        Q(catalog_number_clean__istartswith=search_clean) |
                        Q(artikyl_number_clean__istartswith=search_clean)
                    )
                    if allow_contains:
                        number_search_query |= (
                            Q(catalog_number__icontains=search) |
                            Q(artikyl_number__icontains=search) |
                            Q(cross_number__icontains=search) |
                            Q(cross_number__icontains=search_clean) |
                            Q(catalog_number_clean__icontains=search_clean) |
                            Q(artikyl_number_clean__icontains=search_clean)
                        )
                    if needs_normalization:
                        number_search_query |= (
                            Q(catalog_number__iexact=search_normalized) |
                            Q(artikyl_number__iexact=search_normalized) |
                            Q(cross_number__iexact=search_normalized) |
                            Q(catalog_number_clean__iexact=search_clean_normalized) |
                            Q(artikyl_number_clean__iexact=search_clean_normalized) |
                            Q(catalog_number_clean__istartswith=search_clean_normalized) |
                            Q(artikyl_number_clean__istartswith=search_clean_normalized)
                        )
                        if allow_contains:
                            number_search_query |= (
                                Q(catalog_number__icontains=search_normalized) |
                                Q(artikyl_number__icontains=search_normalized) |
                                Q(cross_number__icontains=search_normalized) |
                                Q(catalog_number_clean__icontains=search_clean_normalized) |
                                Q(artikyl_number_clean__icontains=search_clean_normalized)
                            )
                    
                    oe_search_query = (
                        Q(oe_analogs__oe_kod__iexact=search) |
                        Q(oe_analogs__oe_kod_clean__iexact=search_clean) |
                        Q(oe_analogs__oe_kod_clean__istartswith=search_clean)
                    )
                    if allow_contains:
                        oe_search_query |= (
                            Q(oe_analogs__oe_kod__icontains=search) |
                            Q(oe_analogs__oe_kod_clean__icontains=search_clean)
                        )
                    if needs_normalization:
                        oe_search_query |= (
                            Q(oe_analogs__oe_kod_clean__iexact=search_clean_normalized) |
                            Q(oe_analogs__oe_kod_clean__istartswith=search_clean_normalized)
                        )
                        if allow_contains:
                            oe_search_query |= (
                                Q(oe_analogs__oe_kod_clean__icontains=search_clean_normalized)
                            )
                
                # Находим товары по номерам + по OE аналогам в одном запросе
                found_products = base_queryset.filter(
                    number_search_query | oe_search_query
                ).distinct()
                found_product_ids_set = set(found_products.values_list('id', flat=True))
                
                logger.info("Найдены товары напрямую (по номерам/названию/cross_number)")
                
                # Ищем все OE-аналоги по запросу (для id_tovar); без % — только начало, с % — и в середине
                oe_direct_query = (
                    Q(oe_kod__iexact=search) |
                    Q(oe_kod_clean__iexact=search_clean)
                )
                if len(search_clean) >= 4:
                    oe_direct_query |= Q(oe_kod_clean__istartswith=search_clean)
                if allow_contains:
                    oe_direct_query |= Q(oe_kod__icontains=search) | Q(oe_kod_clean__icontains=search_clean)
                if needs_normalization:
                    oe_direct_query |= (
                        Q(oe_kod__iexact=search_normalized) |
                        Q(oe_kod_clean__iexact=search_clean_normalized)
                    )
                    if len(search_clean_normalized) >= 4:
                        oe_direct_query |= Q(oe_kod_clean__istartswith=search_clean_normalized)
                    if allow_contains:
                        oe_direct_query |= (
                            Q(oe_kod__icontains=search_normalized) |
                            Q(oe_kod_clean__icontains=search_clean_normalized)
                        )
                
                # ИСПРАВЛЕНО: Ищем ВСЕ аналогов (не только без товаров), которые соответствуют поисковому запросу
                # Это позволяет найти родительские товары через id_tovar
                all_matching_oe_analogs = OeKod.objects.filter(oe_direct_query)
                
                products_by_id_tovar = base_queryset.none()  # Инициализируем пустым
                has_products_by_id_tovar = False
                all_oe_codes_from_owners = set()  # НОВОЕ: Собираем все OE коды от владельцев аналогов
                
                # Получаем id_tovar из всех найденных аналогов одним запросом
                id_tovar_list = list(all_matching_oe_analogs.values_list('id_tovar', flat=True).distinct())
                if id_tovar_list:
                    # Убираем суффиксы -dupN для поиска
                    import re
                    clean_id_tovar_list = [re.sub(r'-dup\d+$', '', tid) for tid in id_tovar_list if tid]
                    
                    # Ищем товары по tmp_id (с учетом возможных суффиксов)
                    products_by_id_tovar = base_queryset.filter(
                        Q(tmp_id__in=id_tovar_list) |
                        Q(tmp_id__in=clean_id_tovar_list)
                    ).distinct()
                    
                    has_products_by_id_tovar = products_by_id_tovar.exists()
                    if has_products_by_id_tovar:
                        logger.info("Найдены товары через OE аналоги (по id_tovar)")
                        found_product_ids_set.update(products_by_id_tovar.values_list('id', flat=True))
                        
                        # НОВОЕ: Находим ВСЕ OE аналоги, связанные с найденными товарами (через id_tovar)
                        # Это нужно для поиска товаров по artikyl_number_clean, которые совпадают с oe_kod_clean этих аналогов
                        # Например, если найден товар с id_tovar="000198222", находим все его OE аналоги (включая "20390840")
                        # Затем находим товары с artikyl_number_clean = "20390840"
                        all_owner_oe_analogs = OeKod.objects.filter(
                            Q(id_tovar__in=id_tovar_list) | Q(id_tovar__in=clean_id_tovar_list)
                        ).distinct()
                        
                        # Собираем все oe_kod_clean из этих аналогов
                        for oe in all_owner_oe_analogs:
                            if oe.oe_kod_clean:
                                all_oe_codes_from_owners.add(oe.oe_kod_clean)
                        
                        if all_oe_codes_from_owners:
                            logger.info(f"Найдено {len(all_oe_codes_from_owners)} уникальных OE кодов от владельцев аналогов")
                            logger.info(f"Примеры OE кодов: {list(all_oe_codes_from_owners)[:5]}")
                            
                            # ИСПРАВЛЕНО: Исключаем сам поисковый запрос из списка OE кодов для поиска
                            # (чтобы не дублировать уже найденные товары)
                            oe_codes_for_search = all_oe_codes_from_owners - {search_clean}
                            
                            if oe_codes_for_search:
                                # Находим товары, у которых artikyl_number_clean совпадает с oe_kod_clean найденных аналогов
                                # (кроме самого поискового запроса)
                                products_by_oe_codes = base_queryset.filter(
                                    artikyl_number_clean__in=oe_codes_for_search
                                ).distinct()
                                
                                logger.info("Найдены товары по artikyl_number_clean, совпадающим с OE кодами владельцев (исключая сам запрос)")
                                found_product_ids_set.update(products_by_oe_codes.values_list('id', flat=True))
                
                # Уникальных товаров до группировки (без дублей по разным путям поиска)
                has_found_products = bool(found_product_ids_set)
                if has_found_products:
                    logger.info("Получены уникальные товары до группировки (напрямую/OE/id_tovar)")
                
                # НОВОЕ: Находим ВСЕ аналоги найденных товаров для отображения отдельными карточками
                # Это аналоги, которые принадлежат найденным товарам
                found_analogs = OeKod.objects.none()
                if has_found_products:
                    found_analogs = OeKod.objects.filter(
                        product_id__in=found_product_ids_set
                    ).select_related(
                        'product', 'brand', 'product__brand', 'product__category'
                    ).distinct()
                
                # НОВОЕ: ЛОГИКА ГРУППИРОВКИ для поиска по номерам
                # Согласно ТЗ заказчика:
                # 1. Найти код в artikyl_number_clean (PROPERTY_A) и oe_kod_clean (Name_STR в аналогах)
                # 2. Найти владельцев аналогов (id_tovar)
                # 3. По кодам владельцев (catalog_number_clean/PROPERTY_T и artikyl_number_clean/PROPERTY_A) найти товары
                # 4. По cross_number (PROPERTY_C) найти все товары с одинаковыми значениями
                if has_found_products:
                    # Собираем коды из ВСЕХ найденных товаров (напрямую + через OE аналоги + через id_tovar)
                    found_artikyl_clean_values = set()
                    found_catalog_clean_values = set()  # НОВОЕ: Для поиска по catalog_number_clean (PROPERTY_T)
                    found_catalog_numbers = set()  # Для группировки по catalog_number (Majorsell/CEI)
                    found_cross_numbers = set()  # НОВОЕ: Для поиска по cross_number (PROPERTY_C)
                    
                    # Используем ВСЕ найденные товары для группировки
                    all_found_for_grouping_ids = set(found_product_ids_set)
                    if has_products_by_id_tovar:
                        # Добавляем товары, найденные через id_tovar, если они еще не включены
                        all_found_for_grouping_ids.update(products_by_id_tovar.values_list('id', flat=True))
                    
                    # Собираем artikyl_number_clean (PROPERTY_A) из всех найденных товаров
                    all_found_for_grouping = base_queryset.filter(id__in=all_found_for_grouping_ids)
                    artikyl_clean_data = all_found_for_grouping.values_list('artikyl_number_clean', flat=True)
                    for artikyl_number_clean in artikyl_clean_data:
                        if artikyl_number_clean:
                            found_artikyl_clean_values.add(artikyl_number_clean)
                    
                    # НОВОЕ: Собираем catalog_number_clean (PROPERTY_T) из всех найденных товаров
                    # Это нужно для поиска товаров по кодам владельцев аналогов
                    catalog_clean_data = all_found_for_grouping.values_list('catalog_number_clean', flat=True)
                    for catalog_number_clean in catalog_clean_data:
                        if catalog_number_clean:
                            found_catalog_clean_values.add(catalog_number_clean)
                    
                    # Собираем catalog_number для группировки по Majorsell/CEI
                    catalog_data = all_found_for_grouping.values_list('catalog_number', 'catalog_number_clean', flat=False)
                    for catalog_number, catalog_number_clean in catalog_data:
                        if catalog_number:
                            found_catalog_numbers.add(catalog_number)
                        if catalog_number_clean:
                            found_catalog_numbers.add(catalog_number_clean)
                    
                    # НОВОЕ: Собираем cross_number (PROPERTY_C) из всех найденных товаров
                    cross_data = all_found_for_grouping.values_list('cross_number', flat=True)
                    for cross_number in cross_data:
                        if cross_number and cross_number.strip():
                            found_cross_numbers.add(cross_number.strip())
                    
                    # НОВОЕ: Находим товары по catalog_number_clean (PROPERTY_T) владельцев аналогов
                    # Согласно ТЗ: по кодам владельца найти товары по PROPERTY_T (catalog_number_clean)
                    products_by_catalog_clean = base_queryset.none()
                    if found_catalog_clean_values:
                        products_by_catalog_clean = base_queryset.filter(
                            catalog_number_clean__in=found_catalog_clean_values
                        ).distinct()
                        logger.info("Найдены товары по catalog_number_clean (PROPERTY_T) владельцев аналогов")
                    
                    # НОВОЕ: Находим товары с такими же catalog_number (Majorsell/CEI)
                    # Например, "220169" и "220.169" считаются одинаковыми
                    products_by_catalog = base_queryset.none()
                    if found_catalog_numbers:
                        # Создаем запрос для поиска по catalog_number (с точкой и без)
                        catalog_query = Q()
                        for cat_num in found_catalog_numbers:
                            # Ищем точное совпадение
                            catalog_query |= Q(catalog_number__iexact=cat_num)
                            # Ищем варианты с точкой и без (например, "220169" и "220.169")
                            if '.' in cat_num:
                                # Если есть точка, ищем без точки
                                cat_num_no_dot = cat_num.replace('.', '')
                                catalog_query |= Q(catalog_number__iexact=cat_num_no_dot)
                            else:
                                # Если нет точки, ищем с точкой (добавляем точку в разных местах)
                                # Для "220169" ищем "220.169", "22.0169", "2201.69" и т.д.
                                if len(cat_num) >= 4:
                                    # Простой вариант: добавляем точку после первых 3 символов
                                    cat_num_with_dot = cat_num[:3] + '.' + cat_num[3:]
                                    catalog_query |= Q(catalog_number__iexact=cat_num_with_dot)
                        
                        products_by_catalog = base_queryset.filter(catalog_query).distinct()
                        logger.info("Найдены товары с такими же catalog_number (Majorsell/CEI группировка)")
                    
                    # НОВОЕ: Находим товары по cross_number (PROPERTY_C) владельцев аналогов
                    # Согласно ТЗ: по cross_number найти все товары с одинаковыми значениями
                    products_by_cross = base_queryset.none()
                    if found_cross_numbers:
                        products_by_cross = base_queryset.filter(
                            cross_number__in=found_cross_numbers
                        ).exclude(cross_number='').distinct()
                        logger.info("Найдены товары по cross_number (PROPERTY_C) владельцев аналогов")
                    
                    # Если нашли товары с artikyl_number_clean, находим ВСЕ товары с такими же значениями
                    # ИСПРАВЛЕНО: Группировка по artikyl_number_clean применяется ТОЛЬКО к товарам, найденным напрямую или через OE аналоги
                    if found_artikyl_clean_values:
                        logger.info(f"Найдено уникальных artikyl_number_clean в товарах (напрямую/OE): {len(found_artikyl_clean_values)}")
                        logger.info(f"Значения artikyl_number_clean: {list(found_artikyl_clean_values)[:5]}")
                        
                        # ИСПРАВЛЕНО: Используем artikyl_number_clean для группировки
                        # Это позволяет находить все варианты (с точками и запятыми)
                        products_by_artikyl = base_queryset.filter(
                            artikyl_number_clean__in=found_artikyl_clean_values
                        ).distinct()
                        
                        logger.info("Найдены товары с такими же artikyl_number_clean (группировка по PROPERTY_A)")
                        
                        # Объединяем результаты через id, чтобы избежать дорогих UNION/distinct queryset
                        grouped_ids = set(all_found_for_grouping_ids)
                        grouped_ids.update(products_by_artikyl.values_list('id', flat=True))
                        grouped_ids.update(products_by_catalog_clean.values_list('id', flat=True))
                        grouped_ids.update(products_by_catalog.values_list('id', flat=True))
                        grouped_ids.update(products_by_cross.values_list('id', flat=True))
                        found_product_ids_set = grouped_ids
                        logger.info("Выполнена группировка результатов по PROPERTY_A / PROPERTY_T / PROPERTY_C")
                    else:
                        grouped_ids = set(all_found_for_grouping_ids)
                        grouped_ids.update(products_by_catalog_clean.values_list('id', flat=True))
                        grouped_ids.update(products_by_catalog.values_list('id', flat=True))
                        grouped_ids.update(products_by_cross.values_list('id', flat=True))
                        found_product_ids_set = grouped_ids
                
                # Принудительная дедупликация по id: union в SQLite может давать дубликаты строк
                found_product_ids = list(found_product_ids_set)
                unique_count = len(found_product_ids)
                logger.info(f"Дедупликация по id завершена, уникальных товаров: {unique_count}")
                found_products = base_queryset.filter(id__in=found_product_ids)
                
                logger.info("Результаты поиска и аналоги подготовлены")
                
                # Сохраняем найденные аналоги в атрибуте для использования в get_context_data
                self._found_analogs = found_analogs
                
                if unique_count > 0:
                    queryset = found_products
                    logger.info("Финальный результат: сформирован queryset товаров с аналогами")
                else:
                    # Если по номеру ничего не найдено, возвращаем пустой результат
                    logger.warning(f"По номеру '{search}' ничего не найдено")
                    queryset = base_queryset.none()
                    self._found_analogs = OeKod.objects.none()
            else:
                logger.info(f"Поиск по названию: '{search}'")

                # Режим "по названию": без смешивания с кодовыми полями.
                text_search_query = (
                    Q(name__icontains=search) |
                    Q(applicability__icontains=search)
                )
                queryset = base_queryset.filter(text_search_query).distinct()
                logger.info("Результат поиска по тексту сформирован")
        else:
            # Если поиска нет, применяем фильтры к базовому queryset
            queryset = base_queryset
            logger.info("Поисковый запрос отсутствует, применяем только фильтры")
        
        # Применяем фильтры поверх текущего queryset.
        # Для пустого queryset это безопасно и не меняет результат, но избегает лишнего EXISTS().
        # Фильтр по категории (множественный выбор).
        # Поддерживаем и slug, и id; при выборе родителя включаем товары его подкатегорий.
        category_params = self._get_category_filter_values()
        if category_params:
            raw_values = [(v or '').strip() for v in category_params if (v or '').strip()]
            numeric_ids = [int(v) for v in raw_values if v.isdigit()]
            slug_values = [v for v in raw_values if not v.isdigit()]

            selected_categories_qs = Category.objects.none()
            if numeric_ids:
                selected_categories_qs = selected_categories_qs | Category.objects.filter(id__in=numeric_ids)
            if slug_values:
                selected_categories_qs = selected_categories_qs | Category.objects.filter(slug__in=slug_values)
            selected_categories_qs = selected_categories_qs.distinct()

            selected_ids = set(selected_categories_qs.values_list('id', flat=True))
            all_target_ids = set(selected_ids)

            # Рекурсивно добавляем всех потомков выбранных категорий (по уровням)
            frontier_ids = set(selected_ids)
            while frontier_ids:
                child_ids = set(
                    Category.objects.filter(parent_id__in=frontier_ids, is_active=True).values_list('id', flat=True)
                )
                new_ids = child_ids - all_target_ids
                if not new_ids:
                    break
                all_target_ids.update(new_ids)
                frontier_ids = new_ids

            if all_target_ids:
                queryset = queryset.filter(category_id__in=all_target_ids)
                logger.info(
                    "Применён фильтр по категориям: params=%s, selected=%s, with_descendants=%s",
                    category_params,
                    len(selected_ids),
                    len(all_target_ids),
                )
        
        # Фильтр по бренду (множественный выбор)
        brand_slugs = self._get_brand_filter_values()
        if brand_slugs:
            logger.info(f"Применяем фильтр по брендам: {brand_slugs}")
            queryset = queryset.filter(brand__slug__in=brand_slugs)
            logger.info("Применён фильтр по брендам")
        
        # Фильтр по цене
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            logger.info(f"Применяем фильтр по минимальной цене: {min_price}")
            queryset = queryset.filter(price__gte=min_price)
            logger.info("Применён фильтр по минимальной цене")
        if max_price:
            logger.info(f"Применяем фильтр по максимальной цене: {max_price}")
            queryset = queryset.filter(price__lte=max_price)
            logger.info("Применён фильтр по максимальной цене")

        # Для поиска по номеру: искомый товар (точное совпадение каталожного номера) всегда первым.
        # Остальные результаты (аналоги/группировки) сортируются после него.
        if search and search_is_number and search_priority_clean:
            priority_when = [
                models.When(
                    Q(catalog_number__iexact=search_priority_raw) | Q(catalog_number_clean__iexact=search_priority_clean),
                    then=models.Value(0),
                ),
                models.When(
                    Q(artikyl_number__iexact=search_priority_raw) | Q(artikyl_number_clean__iexact=search_priority_clean),
                    then=models.Value(1),
                ),
            ]
            if search_priority_clean_normalized and search_priority_clean_normalized != search_priority_clean:
                priority_when.append(
                    models.When(
                        Q(catalog_number_clean__iexact=search_priority_clean_normalized) |
                        Q(artikyl_number_clean__iexact=search_priority_clean_normalized),
                        then=models.Value(2),
                    )
                )
                default_priority = 3
            else:
                default_priority = 2
            queryset = queryset.annotate(
                _search_priority=models.Case(
                    *priority_when,
                    default=models.Value(default_priority),
                    output_field=models.IntegerField(),
                )
            )
        
        # Сортировка
        sort = self.request.GET.get('sort', 'newest')
        order_prefix = ['_search_priority'] if (search and search_is_number and search_priority_clean) else []
        if sort == 'price_asc':
            queryset = queryset.order_by(*order_prefix, 'price')
            logger.info("Сортировка по возрастанию цены")
        elif sort == 'price_desc':
            queryset = queryset.order_by(*order_prefix, '-price')
            logger.info("Сортировка по убыванию цены")
        elif sort == 'name':
            queryset = queryset.order_by(*order_prefix, 'name')
            logger.info("Сортировка по названию")
        else:
            queryset = queryset.order_by(*order_prefix, '-created_at')
            logger.info("Сортировка по дате создания (новые сначала)")
        
        # КРИТИЧНО: Применяем distinct() ПОСЛЕ сортировки
        # Это гарантирует удаление дубликатов, которые могут возникнуть
        # при JOIN с таблицей oe_analogs (если у товара несколько OE)
        queryset = queryset.distinct()

        if ids_cache_key:
            # Кэшируем только id + короткий TTL, чтобы не получить протухшие данные надолго.
            cache.set(ids_cache_key, list(queryset.values_list('id', flat=True)), 120)

        logger.info("Финальный queryset каталога сформирован")
        self._queryset_cache = queryset
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        logger.info(f"Формируем контекст для страницы каталога")
        
        # Добавляем найденные аналоги в контекст (если был поиск по номеру)
        if hasattr(self, '_found_analogs'):
            context['found_analogs'] = self._found_analogs
            logger.info("Найденные аналоги добавлены в контекст")
        else:
            context['found_analogs'] = OeKod.objects.none()

        search_query = (self.request.GET.get('search') or '').strip()
        
        # КЕШИРОВАНИЕ: Основные категории (обновляются редко)
        if search_query:
            result_qs = getattr(self, 'object_list', None) or context.get('object_list') or Product.objects.none()
            category_ids_qs = result_qs.order_by().values_list('category_id', flat=True).distinct()
            brand_ids_qs = result_qs.order_by().values_list('brand_id', flat=True).distinct()
            # Для страницы поиска фильтры справа должны показывать только то, что есть в результатах.
            # Категории строим в той же иерархии, но ограничиваем список только найденными id.
            result_category_ids = set(category_ids_qs)
            children_qs = Category.objects.filter(is_active=True).order_by('order', 'name')
            all_main_categories = list(
                Category.objects.filter(parent=None, is_active=True)
                .prefetch_related(Prefetch('children', queryset=children_qs, to_attr='active_children'))
                .order_by('order', 'name')
            )
            main_categories = []
            for parent in all_main_categories:
                matched_children = [c for c in getattr(parent, 'active_children', []) if c.id in result_category_ids]
                if parent.id in result_category_ids or matched_children:
                    parent.active_children = matched_children
                    main_categories.append(parent)
            logger.info(f"Категории фильтра ограничены результатами поиска: {len(main_categories)} корневых")
        else:
            main_categories = cache.get('main_categories')
            if main_categories is None:
                children_qs = Category.objects.filter(is_active=True).order_by('order', 'name')
                main_categories = list(
                    Category.objects.filter(parent=None, is_active=True)
                    .prefetch_related(Prefetch('children', queryset=children_qs, to_attr='active_children'))
                    .order_by('order', 'name')
                )
                cache.set('main_categories', main_categories, settings.CATEGORY_CACHE_TIMEOUT)
                logger.info(f"Основные категории загружены из БД: {len(main_categories)}")
            else:
                logger.info(f"Основные категории загружены из кеша: {len(main_categories)}")
        context['main_categories'] = main_categories
        
        # КЕШИРОВАНИЕ: Все категории для фильтра
        if search_query:
            all_categories = Category.objects.filter(
                is_active=True,
                id__in=category_ids_qs,
            ).order_by('order', 'name')
            logger.info(f"Категории фильтра (по результатам поиска): {all_categories.count()}")
        else:
            all_categories = cache.get('all_categories')
            if all_categories is None:
                all_categories = list(Category.objects.filter(is_active=True).order_by('order', 'name'))
                cache.set('all_categories', all_categories, settings.CATEGORY_CACHE_TIMEOUT)
                logger.info(f"Категории загружены из БД: {len(all_categories)}")
            else:
                logger.info(f"Категории загружены из кеша: {len(all_categories)}")
        context['categories'] = all_categories
        
        # КЕШИРОВАНИЕ: Все бренды для фильтра
        if search_query:
            all_brands = list(Brand.objects.filter(id__in=brand_ids_qs).order_by('name'))
            logger.info(f"Бренды фильтра (по результатам поиска): {len(all_brands)}")
        else:
            all_brands = cache.get('all_brands')
            if all_brands is None:
                all_brands = list(Brand.objects.all().order_by('name'))
                cache.set('all_brands', all_brands, settings.BRAND_CACHE_TIMEOUT)
                logger.info(f"Бренды загружены из БД: {len(all_brands)}")
            else:
                logger.info(f"Бренды загружены из кеша: {len(all_brands)}")
        context['brands'] = all_brands
        # Группировка брендов по первой букве для удобного dropdown-отображения в фильтре
        brand_groups_map = defaultdict(list)
        for brand in all_brands:
            first_char = (brand.name or '').strip()[:1].upper()
            if not first_char:
                first_char = '#'
            # Небуквенные названия отправляем в служебную группу "#"
            if not (('A' <= first_char <= 'Z') or ('А' <= first_char <= 'Я') or first_char == 'Ё'):
                first_char = '#'
            brand_groups_map[first_char].append(brand)
        context['brand_groups'] = sorted(
            brand_groups_map.items(),
            key=lambda item: (item[0] == '#', item[0]),
        )
        
        # Выбранные фильтры для template
        context['current_category'] = getattr(self, 'category', None)
        context['current_brand'] = getattr(self, 'brand', None)
        if self.brand:
            context['catalog_form_action'] = reverse(
                'shop:brand',
                kwargs={'brand_slug': self.brand.slug},
            )
        elif self.category:
            context['catalog_form_action'] = reverse(
                'shop:category',
                kwargs={'category_slug': self.category.slug},
            )
        else:
            context['catalog_form_action'] = reverse('shop:catalog')
        context['selected_categories'] = self._get_category_filter_values()
        context['selected_brands'] = self._get_brand_filter_values()
        # Количество активных фильтров (для мобильной кнопки «ФИЛЬТРЫ (N)»)
        n = len(context['selected_categories']) + len(context['selected_brands'])
        if self.request.GET.get('min_price') or self.request.GET.get('max_price'):
            n += 1
        if self.request.GET.get('sort') and self.request.GET.get('sort') != 'newest':
            n += 1
        context['active_filters_count'] = n
        logger.info(f"Выбранные категории: {context['selected_categories']}")
        logger.info(f"Выбранные бренды: {context['selected_brands']}")
        
        # Поисковый запрос
        context['search_query'] = self.request.GET.get('search', '')
        context['search_mode'] = _normalize_search_mode(self.request.GET.get('search_mode'))
        if context['search_query']:
            logger.info(f"Поисковый запрос в контексте: '{context['search_query']}'")
        
        # Минимальная и максимальная цена для фильтра
        if context['products']:
            context['min_price'] = context['products'].aggregate(min_price=models.Min('price'))['min_price']
            context['max_price'] = context['products'].aggregate(max_price=models.Max('price'))['max_price']
            logger.info(f"Диапазон цен: {context['min_price']} - {context['max_price']}")
        
        logger.info("Контекст каталога сформирован")
        return context


class ProductView(ProductSEOMixin, DetailView):
    """
    Страница товара с SEO оптимизацией
    """
    model = Product
    template_name = 'product.html'
    context_object_name = 'product'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        """
        ОПТИМИЗАЦИЯ: загружаем связанные данные за один запрос
        """
        return Product.objects.select_related(
            'category', 'brand'
        ).prefetch_related(
            'images',
            'oe_analogs',
            'oe_analogs__brand',
            'oe_analogs__product',
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        cross_sort_param = self.request.GET.get('cross_sort', '').strip() or 'brand'
        cache_key = f'product:context:{product.slug}:{cross_sort_param}'
        cached = cache.get(cache_key)
        if cached:
            context.update(cached)
            return context

        # Для каждой строки кросс-номеров — ссылка на один конкретный товар-аналог (страница товара, не поиск)
        oe_analogs_with_url = []
        if product.oe_analogs.exists():
            oe_cleans = list({o.oe_kod_clean for o in product.oe_analogs.all() if o.oe_kod_clean})
            if oe_cleans:
                # Prefetch только нужных аналогов по oe_cleans — меньше данных (п. 1.3)
                prefetch_oe = Prefetch(
                    'oe_analogs',
                    queryset=OeKod.objects.filter(oe_kod_clean__in=oe_cleans).only(
                        'id', 'oe_kod_clean', 'brand_id', 'product_id'
                    ),
                )
                candidates = Product.objects.filter(
                    in_stock=True,
                    oe_analogs__oe_kod_clean__in=oe_cleans,
                ).exclude(id=product.id).only('id', 'slug').distinct().prefetch_related(prefetch_oe)[:300]
                by_oe_brand = {}
                for p in candidates:
                    for o in p.oe_analogs.filter(oe_kod_clean__in=oe_cleans):
                        key = (o.oe_kod_clean, o.brand_id or 0)
                        if key not in by_oe_brand:
                            by_oe_brand[key] = p
            else:
                by_oe_brand = {}
            for analog in product.oe_analogs.all():
                key = (analog.oe_kod_clean, analog.brand_id or 0) if analog.oe_kod_clean else (None, 0)
                p = by_oe_brand.get(key) if key[0] else None
                if not p and analog.oe_kod_clean:
                    p = by_oe_brand.get((analog.oe_kod_clean, 0))
                if not p and analog.oe_kod_clean:
                    for k, v in by_oe_brand.items():
                        if k[0] == analog.oe_kod_clean:
                            p = v
                            break
                url = p.get_absolute_url() if p else None
                oe_analogs_with_url.append({'analog': analog, 'url': url})

        # Сортировка и пагинация кросс-номеров (как на скриншоте заказчика)
        cross_sort = (self.request.GET.get('cross_sort') or 'brand').strip()
        if cross_sort not in ('brand', '-brand', 'article', '-article'):
            cross_sort = 'brand'
        if cross_sort == 'brand':
            oe_analogs_with_url.sort(key=lambda x: (x['analog'].brand.name if x['analog'].brand else '\uffff', x['analog'].oe_kod or ''))
        elif cross_sort == '-brand':
            oe_analogs_with_url.sort(key=lambda x: (x['analog'].brand.name if x['analog'].brand else '', x['analog'].oe_kod or ''), reverse=True)
        elif cross_sort == 'article':
            oe_analogs_with_url.sort(key=lambda x: (x['analog'].oe_kod or '', x['analog'].brand.name if x['analog'].brand else ''))
        else:  # -article
            oe_analogs_with_url.sort(key=lambda x: (x['analog'].oe_kod or '', x['analog'].brand.name if x['analog'].brand else ''), reverse=True)

        context['oe_analogs_with_url'] = oe_analogs_with_url
        context['cross_sort'] = cross_sort
        context['open_cross_tab'] = bool(
            product.oe_analogs.exists() and self.request.GET.get('cross_sort')
        )

        # Похожие товары (из той же категории)
        related_products = Product.objects.filter(
            category=product.category,
            in_stock=True
        ).exclude(id=product.id).select_related('brand').prefetch_related('images')[:6]
        context['related_products'] = related_products

        # Кеш контекста на 5–10 мин (п. 1.2)
        cache.set(cache_key, {
            'oe_analogs_with_url': context['oe_analogs_with_url'],
            'cross_sort': context['cross_sort'],
            'open_cross_tab': context['open_cross_tab'],
            'related_products': context['related_products'],
        }, getattr(settings, 'PRODUCT_CACHE_TIMEOUT', 300))

        return context
