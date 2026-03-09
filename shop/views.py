from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView
from django.db.models import Q, Prefetch
from django.db import models
from django.core.cache import cache
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Product, Category, Brand, OeKod
from .seo import ProductSEOMixin, CategorySEOMixin, SEOMixin
import logging
import re

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


@require_GET
def search_autocomplete(request):
    """
    Асинхронные подсказки для поиска (autocomplete).
    GET-параметр q — строка запроса (минимум 2 символа).
    По номерам: по умолчанию только по началу; с % в запросе — и в середине.
    """
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'suggestions': []})

    q_work, allow_contains = _parse_search_mode(q)
    q_normalized = normalize_latin_to_cyrillic(q_work)
    q_clean = Product.clean_number(q_work)
    q_clean_norm = Product.clean_number(q_normalized)
    suggestions = []
    seen_values = set()
    max_items = 10

    # Подсказки: название — по подстроке; номера — по началу, с % в запросе ещё и в середине
    number_q = (
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
        number_q |= (
            Q(catalog_number__icontains=q_normalized) |
            Q(catalog_number_clean__icontains=q_clean) |
            Q(artikyl_number__icontains=q_work) |
            Q(artikyl_number_clean__icontains=q_clean)
        )
    product_q = Q(name__icontains=q_normalized) | number_q
    products = Product.objects.filter(in_stock=True).filter(product_q)
    # Если передан бренд (напр. с каталога с выбранным фильтром) — ищем только в нём
    brand_slug = request.GET.get('brand', '').strip()
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

    # Подсказки по брендам (если ещё есть место)
    if len(suggestions) < max_items:
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

    return JsonResponse({'suggestions': suggestions})


class CatalogView(CategorySEOMixin, ListView):
    """
    Каталог товаров с SEO оптимизацией
    """
    model = Product
    template_name = 'catalog.html'
    context_object_name = 'products'
    paginate_by = 100
    
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

        # Инициализируем список найденных аналогов
        self._found_analogs = OeKod.objects.none()
        
        # Начинаем с базового queryset с оптимизацией
        base_queryset = Product.objects.filter(
            in_stock=True
        ).select_related(
            'category', 'brand'
        ).prefetch_related(
            'oe_analogs', 'oe_analogs__brand'
        )
        
        # Не вызываем .count() в проде — лишний тяжёлый запрос (оптимизация)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Базовый queryset: {base_queryset.count()} товаров")
        
        # Поиск согласно ТЗ (приоритет поиска выше фильтров)
        search = self.request.GET.get('search')
        if search:
            search = search.strip()
            # Без % — только по началу номера; с % — и в середине (как в подсказках)
            search, allow_contains = _parse_search_mode(search)
            logger.info(f"Поисковый запрос: '{search}' (поиск в середине: {allow_contains})")
            
            # Определяем является ли запрос поиском по номеру
            if OeKod.is_number_search(search):
                logger.info(f"Поиск по номеру: '{search}'")
                
                # КРИТИЧНО: Очищаем поисковый запрос от символов
                search_clean = Product.clean_number(search)
                logger.info(f"Очищенный запрос: '{search_clean}'")
                
                # ИСПРАВЛЕНИЕ: Создаем нормализованную версию (Latin → Cyrillic)
                # Для случаев типа "Яблоко M16/8" (Latin M) → "Яблоко М16/8" (Cyrillic М)
                search_normalized = normalize_latin_to_cyrillic(search)
                search_clean_normalized = Product.clean_number(search_normalized)
                
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
                        Q(name__icontains=search) |
                        Q(name__icontains=search_clean) |
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
                
                logger.info(f"Найдено товаров напрямую (по номерам/названию/cross_number): {found_products.count()}")
                
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
                all_oe_codes_from_owners = set()  # НОВОЕ: Собираем все OE коды от владельцев аналогов
                
                if all_matching_oe_analogs.exists():
                    # Получаем id_tovar из всех найденных аналогов
                    id_tovar_list = list(all_matching_oe_analogs.values_list('id_tovar', flat=True).distinct())
                    # Убираем суффиксы -dupN для поиска
                    import re
                    clean_id_tovar_list = [re.sub(r'-dup\d+$', '', tid) for tid in id_tovar_list if tid]
                    
                    # Ищем товары по tmp_id (с учетом возможных суффиксов)
                    products_by_id_tovar = base_queryset.filter(
                        Q(tmp_id__in=id_tovar_list) |
                        Q(tmp_id__in=clean_id_tovar_list)
                    ).distinct()
                    
                    if products_by_id_tovar.exists():
                        logger.info(f"Найдено {products_by_id_tovar.count()} товаров через OE аналоги (по id_tovar)")
                        found_products = (found_products | products_by_id_tovar).distinct()
                        
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
                                
                                if products_by_oe_codes.exists():
                                    logger.info(f"Найдено {products_by_oe_codes.count()} товаров по artikyl_number_clean, совпадающим с OE кодами владельцев (исключая сам запрос)")
                                    found_products = (found_products | products_by_oe_codes).distinct()
                
                # Уникальных товаров до группировки (без дублей по разным путям поиска)
                if found_products.exists():
                    logger.info(f"Уникальных товаров до группировки (напрямую/OE/id_tovar): {found_products.count()}")
                
                # НОВОЕ: Находим ВСЕ аналоги найденных товаров для отображения отдельными карточками
                # Это аналоги, которые принадлежат найденным товарам
                found_analogs = OeKod.objects.none()
                if found_products.exists():
                    found_product_ids = found_products.values_list('id', flat=True)
                    found_analogs = OeKod.objects.filter(
                        product_id__in=found_product_ids
                    ).select_related(
                        'product', 'brand', 'product__brand', 'product__category'
                    ).distinct()
                
                # НОВОЕ: ЛОГИКА ГРУППИРОВКИ для поиска по номерам
                # Согласно ТЗ заказчика:
                # 1. Найти код в artikyl_number_clean (PROPERTY_A) и oe_kod_clean (Name_STR в аналогах)
                # 2. Найти владельцев аналогов (id_tovar)
                # 3. По кодам владельцев (catalog_number_clean/PROPERTY_T и artikyl_number_clean/PROPERTY_A) найти товары
                # 4. По cross_number (PROPERTY_C) найти все товары с одинаковыми значениями
                if found_products.exists():
                    # Собираем коды из ВСЕХ найденных товаров (напрямую + через OE аналоги + через id_tovar)
                    found_artikyl_clean_values = set()
                    found_catalog_clean_values = set()  # НОВОЕ: Для поиска по catalog_number_clean (PROPERTY_T)
                    found_catalog_numbers = set()  # Для группировки по catalog_number (Majorsell/CEI)
                    found_cross_numbers = set()  # НОВОЕ: Для поиска по cross_number (PROPERTY_C)
                    
                    # Используем ВСЕ найденные товары для группировки
                    all_found_for_grouping = found_products
                    if products_by_id_tovar.exists():
                        # Добавляем товары, найденные через id_tovar, если они еще не включены
                        all_found_for_grouping = (all_found_for_grouping | products_by_id_tovar).distinct()
                    
                    # Собираем artikyl_number_clean (PROPERTY_A) из всех найденных товаров
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
                        if products_by_catalog_clean.exists():
                            logger.info(f"Найдено {products_by_catalog_clean.count()} товаров по catalog_number_clean (PROPERTY_T) владельцев аналогов")
                    
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
                        if products_by_catalog.exists():
                            logger.info(f"Найдено {products_by_catalog.count()} товаров с такими же catalog_number (Majorsell/CEI группировка)")
                    
                    # НОВОЕ: Находим товары по cross_number (PROPERTY_C) владельцев аналогов
                    # Согласно ТЗ: по cross_number найти все товары с одинаковыми значениями
                    products_by_cross = base_queryset.none()
                    if found_cross_numbers:
                        products_by_cross = base_queryset.filter(
                            cross_number__in=found_cross_numbers
                        ).exclude(cross_number='').distinct()
                        if products_by_cross.exists():
                            logger.info(f"Найдено {products_by_cross.count()} товаров по cross_number (PROPERTY_C) владельцев аналогов")
                    
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
                        
                        if products_by_artikyl.exists():
                            logger.info(f"Найдено {products_by_artikyl.count()} товаров с такими же artikyl_number_clean (группировка по PROPERTY_A)")
                            
                            # ИСПРАВЛЕНО: Объединяем товары, найденные напрямую/OE + группировку по artikyl_number_clean + 
                            # группировку по catalog_number_clean (PROPERTY_T) + группировку по catalog_number (Majorsell/CEI) + группировку по cross_number (PROPERTY_C)
                            found_products = (
                                all_found_for_grouping | 
                                products_by_artikyl | 
                                products_by_catalog_clean | 
                                products_by_catalog | 
                                products_by_cross
                            ).distinct()
                            initial_count = all_found_for_grouping.count()
                            artikyl_count = products_by_artikyl.count()
                            catalog_clean_count = products_by_catalog_clean.count() if products_by_catalog_clean.exists() else 0
                            catalog_count = products_by_catalog.count() if products_by_catalog.exists() else 0
                            cross_count = products_by_cross.count() if products_by_cross.exists() else 0
                            added_by_artikyl = artikyl_count - initial_count
                            logger.info(f"Исходных результатов: {initial_count}, добавлено по artikyl_number: {added_by_artikyl}, по catalog_number_clean: {catalog_clean_count}, по catalog_number: {catalog_count}, по cross_number: {cross_count}, итого: {found_products.count()}")
                        else:
                            # Если нет группировки по artikyl_number_clean, добавляем товары по catalog_number_clean, catalog_number и cross_number
                            found_products = (
                                all_found_for_grouping | 
                                products_by_catalog_clean | 
                                products_by_catalog | 
                                products_by_cross
                            ).distinct()
                    else:
                        # Если нет artikyl_number_clean для группировки, добавляем товары по catalog_number_clean, catalog_number и cross_number
                        found_products = (
                            all_found_for_grouping | 
                            products_by_catalog_clean | 
                            products_by_catalog | 
                            products_by_cross
                        ).distinct()
                
                # Принудительная дедупликация по id: union в SQLite может давать дубликаты строк
                found_product_ids = list(found_products.values_list('id', flat=True).distinct())
                unique_count = len(found_product_ids)
                if unique_count != found_products.count():
                    logger.info(f"Дедупликация по id: было {found_products.count()} строк, уникальных товаров: {unique_count}")
                found_products = base_queryset.filter(id__in=found_product_ids)
                
                products_count = found_products.count()
                analogs_count = found_analogs.count()
                logger.info(f"Найдено товаров: {products_count}, аналогов этих товаров: {analogs_count}")
                
                # Сохраняем найденные аналоги в атрибуте для использования в get_context_data
                self._found_analogs = found_analogs
                
                if found_products.exists() or found_analogs.exists():
                    queryset = found_products
                    logger.info(f"Финальный результат: {queryset.count()} товаров, {analogs_count} аналогов")
                else:
                    # Если по номеру ничего не найдено, возвращаем пустой результат
                    logger.warning(f"По номеру '{search}' ничего не найдено")
                    queryset = base_queryset.none()
                    self._found_analogs = OeKod.objects.none()
            else:
                logger.info(f"Поиск по тексту: '{search}'")
                
                # ИСПРАВЛЕНО: Для SQLite icontains может не работать корректно с кириллицей
                # Используем оба варианта: оригинальный и в нижнем регистре
                search_lower = search.lower()
                search_upper = search.upper()
                search_capitalize = search.capitalize()
                # НОВОЕ: Очищенная версия для поиска в очищенных полях
                search_clean = Product.clean_number(search)
                
                # ПОИСК ПО НАЗВАНИЮ И БРЕНДУ - ищем по ВСЕМ товарам независимо от фильтров
                # ИСПРАВЛЕНО: Добавлен поиск по artikyl_number и artikyl_number_clean (PROPERTY_A)
                # ИСПРАВЛЕНО: Добавлен поиск по OE кодам в текстовой логике (для случаев типа "fynbktl")
                # Пробуем все варианты регистра для надежности
                text_search_query = (
                    Q(name__icontains=search) |
                    Q(name__icontains=search_lower) |
                    Q(name__icontains=search_upper) |
                    Q(name__icontains=search_capitalize) |
                    Q(brand__name__icontains=search) |
                    Q(brand__name__icontains=search_lower) |
                    Q(brand__name__icontains=search_upper) |
                    Q(brand__name__icontains=search_capitalize) |
                    Q(description__icontains=search) |
                    Q(description__icontains=search_lower) |
                    Q(applicability__icontains=search) |
                    Q(applicability__icontains=search_lower) |
                    # НОВОЕ: Поиск по дополнительному номеру (PROPERTY_A) - оригинальное поле
                    Q(artikyl_number__icontains=search) |
                    Q(artikyl_number__icontains=search_lower) |
                    Q(artikyl_number__icontains=search_upper) |
                    Q(artikyl_number__icontains=search_capitalize) |
                    # НОВОЕ: Поиск по очищенному дополнительному номеру (без символов и регистра)
                    Q(artikyl_number_clean__icontains=search_clean) |
                    # НОВОЕ: Поиск по каталожному номеру (на случай если там текст)
                    Q(catalog_number__icontains=search) |
                    Q(catalog_number__icontains=search_lower) |
                    Q(catalog_number_clean__icontains=search_clean) |
                    # НОВОЕ: Поиск по OE кодам (для случаев типа "fynbktl" - только буквы)
                    Q(oe_analogs__oe_kod__icontains=search) |
                    Q(oe_analogs__oe_kod__icontains=search_lower) |
                    Q(oe_analogs__oe_kod__icontains=search_upper) |
                    Q(oe_analogs__oe_kod_clean__icontains=search_clean)
                )
                
                # НОВОЕ: ЛОГИКА ГРУППИРОВКИ ПО PROPERTY_A (artikyl_number)
                # Если найдены товары (по любому полю, включая OE коды), проверяем их artikyl_number
                # и находим ВСЕ товары с такими же значениями artikyl_number/artikyl_number_clean
                initial_results = base_queryset.filter(text_search_query).distinct()
                
                # ИСПРАВЛЕНО: Также находим товары через OE коды, если они не попали в initial_results
                # Это нужно для случаев типа "fynbktl" - когда товар найден только через OE код
                oe_products = base_queryset.filter(
                    Q(oe_analogs__oe_kod__icontains=search) |
                    Q(oe_analogs__oe_kod__icontains=search_lower) |
                    Q(oe_analogs__oe_kod__icontains=search_upper) |
                    Q(oe_analogs__oe_kod_clean__icontains=search_clean)
                ).distinct()
                
                # Объединяем все найденные товары
                all_found_products = (initial_results | oe_products).distinct()
                
                # Находим уникальные значения artikyl_number и artikyl_number_clean из найденных товаров
                # Это работает для товаров, найденных по названию, artikyl_number, OE кодам или любому другому полю
                # ИСПРАВЛЕНО: Используем values_list вместо only() чтобы избежать конфликта с select_related
                found_artikyl_values = set()
                found_artikyl_clean_values = set()
                
                # Загружаем artikyl_number из найденных товаров (используем values_list для эффективности)
                artikyl_data = all_found_products.values_list('artikyl_number', 'artikyl_number_clean', flat=False)
                for artikyl_number, artikyl_number_clean in artikyl_data:
                    if artikyl_number:
                        found_artikyl_values.add(artikyl_number)
                    if artikyl_number_clean:
                        found_artikyl_clean_values.add(artikyl_number_clean)
                
                # Если нашли товары с artikyl_number, добавляем все товары с такими же значениями
                if found_artikyl_values or found_artikyl_clean_values:
                    logger.info(f"Найдено уникальных artikyl_number: {len(found_artikyl_values)}, artikyl_number_clean: {len(found_artikyl_clean_values)}")
                    
                    # Поиск всех товаров с такими же artikyl_number
                    # ИСПРАВЛЕНО: Используем artikyl_number_clean для поиска всех вариантов (с точками и запятыми)
                    artikyl_query = Q()
                    if found_artikyl_clean_values:
                        artikyl_query |= Q(artikyl_number_clean__in=found_artikyl_clean_values)
                    # Также добавляем оригинальные значения для совместимости
                    if found_artikyl_values:
                        artikyl_query |= Q(artikyl_number__in=found_artikyl_values)
                    
                    # Добавляем все товары с такими же artikyl_number
                    products_by_artikyl = base_queryset.filter(artikyl_query).distinct()
                    
                    if products_by_artikyl.exists():
                        logger.info(f"Найдено {products_by_artikyl.count()} товаров с такими же artikyl_number (группировка по PROPERTY_A)")
                        # Объединяем результаты: исходные + все товары с такими же artikyl_number
                        queryset = (all_found_products | products_by_artikyl).distinct()
                    else:
                        queryset = all_found_products
                else:
                    queryset = all_found_products
                
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
        
        # КРИТИЧНО: Применяем distinct() ПОСЛЕ сортировки
        # Это гарантирует удаление дубликатов, которые могут возникнуть
        # при JOIN с таблицей oe_analogs (если у товара несколько OE)
        queryset = queryset.distinct()

        logger.info(f"Финальный результат: {queryset.count()} товаров")
        self._queryset_cache = queryset
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        logger.info(f"Формируем контекст для страницы каталога")
        
        # Добавляем найденные аналоги в контекст (если был поиск по номеру)
        if hasattr(self, '_found_analogs'):
            context['found_analogs'] = self._found_analogs
            logger.info(f"Добавлено {self._found_analogs.count()} аналогов в контекст")
        else:
            context['found_analogs'] = OeKod.objects.none()
        
        # КЕШИРОВАНИЕ: Основные категории (обновляются редко)
        main_categories = cache.get('main_categories')
        if main_categories is None:
            main_categories = list(Category.objects.filter(parent=None, is_active=True).order_by('order', 'name'))
            cache.set('main_categories', main_categories, settings.CATEGORY_CACHE_TIMEOUT)
            logger.info(f"Основные категории загружены из БД: {len(main_categories)}")
        else:
            logger.info(f"Основные категории загружены из кеша: {len(main_categories)}")
        context['main_categories'] = main_categories
        
        # КЕШИРОВАНИЕ: Все категории для фильтра
        all_categories = cache.get('all_categories')
        if all_categories is None:
            all_categories = list(Category.objects.filter(is_active=True).order_by('order', 'name'))
            cache.set('all_categories', all_categories, settings.CATEGORY_CACHE_TIMEOUT)
            logger.info(f"Категории загружены из БД: {len(all_categories)}")
        else:
            logger.info(f"Категории загружены из кеша: {len(all_categories)}")
        context['categories'] = all_categories
        
        # КЕШИРОВАНИЕ: Все бренды для фильтра
        all_brands = cache.get('all_brands')
        if all_brands is None:
            all_brands = list(Brand.objects.all().order_by('name'))
            cache.set('all_brands', all_brands, settings.BRAND_CACHE_TIMEOUT)
            logger.info(f"Бренды загружены из БД: {len(all_brands)}")
        else:
            logger.info(f"Бренды загружены из кеша: {len(all_brands)}")
        context['brands'] = all_brands
        
        # Выбранные фильтры для template
        context['selected_categories'] = self.request.GET.getlist('category')
        context['selected_brands'] = self.request.GET.getlist('brand')
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
        if context['search_query']:
            logger.info(f"Поисковый запрос в контексте: '{context['search_query']}'")
        
        # Минимальная и максимальная цена для фильтра
        if context['products']:
            context['min_price'] = context['products'].aggregate(min_price=models.Min('price'))['min_price']
            context['max_price'] = context['products'].aggregate(max_price=models.Max('price'))['max_price']
            logger.info(f"Диапазон цен: {context['min_price']} - {context['max_price']}")
        
        logger.info(f"Контекст сформирован, товаров в контексте: {context['products'].count() if context['products'] else 0}")
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
