#!/bin/bash

# Скрипт для настройки и тестирования проекта
# Запустите в терминале: bash setup_and_test.sh

echo "🚀 НАСТРОЙКА И ТЕСТИРОВАНИЕ ПРОЕКТА TIR-LUGANSK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Переходим в директорию проекта
cd /Users/ast_mav/Documents/For_work/tir-lugansk

echo ""
echo "${BLUE}📦 ШАГ 1: УСТАНОВКА ЗАВИСИМОСТЕЙ${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Устанавливаем пакеты из requirements.txt..."
pip3 install -r requirements.txt --user

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Зависимости установлены${NC}"
else
    echo -e "${RED}❌ Ошибка установки зависимостей${NC}"
    echo "Попробуйте вручную: pip3 install -r requirements.txt"
    exit 1
fi

echo ""
echo "${BLUE}🗄️ ШАГ 2: ПРОВЕРКА МИГРАЦИЙ${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 manage.py showmigrations shop

echo ""
echo "Создаём новые миграции (если нужно)..."
python3 manage.py makemigrations shop

echo ""
echo "Применяем миграции..."
python3 manage.py migrate

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Миграции применены${NC}"
else
    echo -e "${RED}❌ Ошибка применения миграций${NC}"
    exit 1
fi

echo ""
echo "${BLUE}📊 ШАГ 3: ПРОВЕРКА БАЗЫ ДАННЫХ${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 manage.py shell -c "
from shop.models import Product, Brand, OeKod, ProductImage, Category

print()
print('📊 ТЕКУЩЕЕ СОСТОЯНИЕ БАЗЫ ДАННЫХ:')
print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
products_count = Product.objects.count()
brands_count = Brand.objects.count()
categories_count = Category.objects.count()
oe_count = OeKod.objects.count()
images_count = ProductImage.objects.count()

print(f'✅ Товаров: {products_count}')
print(f'✅ Брендов: {brands_count}')
print(f'✅ Категорий: {categories_count}')
print(f'✅ OE аналогов: {oe_count}')
print(f'✅ Изображений: {images_count}')
print()

# Проверяем новые поля
if products_count > 0:
    print('🔍 ПРОВЕРКА НОВЫХ ПОЛЕЙ:')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    
    # Проверяем catalog_number_clean
    with_clean_catalog = Product.objects.exclude(catalog_number_clean='').count()
    with_clean_artikyl = Product.objects.exclude(artikyl_number_clean='').count()
    
    print(f'   • Товаров с catalog_number_clean: {with_clean_catalog}')
    print(f'   • Товаров с artikyl_number_clean: {with_clean_artikyl}')
    print()
    
    # Показываем примеры
    print('📋 ПРИМЕРЫ ТОВАРОВ:')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    for p in Product.objects.all()[:5]:
        brand_name = p.brand.name if p.brand else 'Без бренда'
        cat_clean = p.catalog_number_clean or 'нет'
        print(f'   • {p.name[:50]}')
        print(f'     Бренд: {brand_name}')
        print(f'     Каталожный номер: {p.catalog_number} → {cat_clean}')
        print()

if oe_count > 0:
    print('🔗 ПРИМЕРЫ OE АНАЛОГОВ:')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    for oe in OeKod.objects.select_related('product', 'brand')[:5]:
        brand_name = oe.brand.name if oe.brand else 'Без бренда'
        print(f'   • {oe.product.name[:40]} → {brand_name} {oe.oe_kod}')
    print()
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ База данных проверена${NC}"
else
    echo -e "${RED}❌ Ошибка проверки БД${NC}"
fi

echo ""
echo "${BLUE}🔍 ШАГ 4: ПРОВЕРКА ОЧИЩЕННЫХ НОМЕРОВ${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 manage.py shell -c "
from shop.models import Product

products_with_catalog = Product.objects.filter(catalog_number__isnull=False).exclude(catalog_number='')
total = products_with_catalog.count()
with_clean = products_with_catalog.exclude(catalog_number_clean='').count()

print(f'Товаров с каталожным номером: {total}')
print(f'Товаров с очищенным номером: {with_clean}')
print()

if total > 0 and with_clean == 0:
    print('⚠️  ВНИМАНИЕ: Очищенные номера НЕ заполнены!')
    print('   Запустите: python3 manage.py populate_clean_numbers')
elif total == with_clean:
    print('✅ Все очищенные номера заполнены!')
else:
    print(f'⚠️  Заполнено: {(with_clean/total*100):.1f}%')
    print('   Рекомендуется запустить: python3 manage.py populate_clean_numbers')
"

echo ""
echo "${BLUE}🧪 ШАГ 5: ТЕСТИРОВАНИЕ ПОИСКА${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 manage.py shell -c "
from shop.models import Product
import time

print('Тестируем поиск...')
print()

# Тест 1: Получаем примеры номеров
sample = Product.objects.exclude(catalog_number='').first()
if sample and sample.catalog_number:
    search_num = sample.catalog_number
    search_clean = sample.catalog_number_clean
    
    print(f'🔎 Тестовый номер: {search_num}')
    print(f'   Очищенный: {search_clean}')
    print()
    
    # Поиск по оригиналу
    start = time.time()
    results1 = Product.objects.filter(catalog_number__iexact=search_num).count()
    time1 = (time.time() - start) * 1000
    
    # Поиск по очищенному
    if search_clean:
        start = time.time()
        results2 = Product.objects.filter(catalog_number_clean__iexact=search_clean).count()
        time2 = (time.time() - start) * 1000
        
        print(f'✅ Поиск по оригиналу: {results1} за {time1:.2f}ms')
        print(f'✅ Поиск по очищенному: {results2} за {time2:.2f}ms')
        print()
        
        if time2 < time1:
            print(f'🚀 Очищенный поиск быстрее на {((time1-time2)/time1*100):.1f}%')
    else:
        print('⚠️  Очищенный номер пустой - запустите populate_clean_numbers')
else:
    print('⚠️  Нет товаров с каталожными номерами для теста')
"

echo ""
echo "${BLUE}📸 ШАГ 6: ПРОВЕРКА ИЗОБРАЖЕНИЙ${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -d "images" ]; then
    image_count=$(find images -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" \) 2>/dev/null | wc -l)
    echo -e "${GREEN}✅ Папка images найдена${NC}"
    echo "   Найдено файлов изображений: $image_count"
    
    if [ $image_count -gt 0 ]; then
        echo ""
        echo "   Хотите связать изображения с товарами?"
        echo "   Запустите: python3 manage.py link_product_images --dry-run"
    fi
else
    echo -e "${YELLOW}⚠️  Папка images не найдена${NC}"
    echo "   Изображения должны быть в: /Users/ast_mav/Documents/For_work/tir-lugansk/images/"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}🎉 ПРОВЕРКА ЗАВЕРШЕНА!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 СЛЕДУЮЩИЕ ШАГИ:"
echo ""
echo "1️⃣  Если очищенные номера НЕ заполнены:"
echo "   ${YELLOW}python3 manage.py populate_clean_numbers${NC}"
echo ""
echo "2️⃣  Если нужно связать изображения (тестовый режим):"
echo "   ${YELLOW}python3 manage.py link_product_images --dry-run${NC}"
echo ""
echo "3️⃣  Запустить сервер:"
echo "   ${YELLOW}python3 manage.py runserver${NC}"
echo "   Откройте: http://localhost:8000/admin/"
echo ""
echo "4️⃣  Протестировать поиск на сайте:"
echo "   Откройте каталог и попробуйте поиск по номерам"
echo ""
echo "📖 Полная документация: DEPLOYMENT_GUIDE.md"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

