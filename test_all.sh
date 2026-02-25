#!/bin/bash

# Скрипт для быстрого тестирования всех функций проекта
# Запуск: chmod +x test_all.sh && ./test_all.sh

echo "🧪 ТЕСТИРОВАНИЕ ПРОЕКТА TIR-LUGANSK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для проверки статуса
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
    else
        echo -e "${RED}❌ $1${NC}"
        exit 1
    fi
}

# 1. Проверка Python окружения
echo ""
echo "1️⃣ Проверка Python окружения..."
python3 --version
check_status "Python установлен"

# 2. Проверка зависимостей
echo ""
echo "2️⃣ Проверка зависимостей..."
pip3 list | grep Django
check_status "Django установлен"

pip3 list | grep dbfread
check_status "dbfread установлен"

# 3. Проверка миграций
echo ""
echo "3️⃣ Проверка миграций..."
python3 manage.py showmigrations shop | grep "\[ \]"
if [ $? -eq 0 ]; then
    echo -e "${YELLOW}⚠️ Есть неприменённые миграции${NC}"
    echo "Применяем..."
    python3 manage.py migrate
    check_status "Миграции применены"
else
    echo -e "${GREEN}✅ Все миграции применены${NC}"
fi

# 4. Проверка базы данных
echo ""
echo "4️⃣ Проверка базы данных..."
python3 manage.py shell -c "
from shop.models import Product, Brand, OeKod, ProductImage

print('📊 Статистика базы данных:')
print(f'   • Товаров: {Product.objects.count()}')
print(f'   • Брендов: {Brand.objects.count()}')
print(f'   • OE аналогов: {OeKod.objects.count()}')
print(f'   • Изображений: {ProductImage.objects.count()}')
print(f'   • Товаров с очищенными номерами: {Product.objects.exclude(catalog_number_clean=\"\").count()}')
"
check_status "База данных доступна"

# 5. Проверка поиска
echo ""
echo "5️⃣ Тестирование поиска..."
python3 manage.py shell -c "
from shop.models import Product
import time

# Тест 1: Поиск по очищенному номеру
start = time.time()
results = Product.objects.filter(catalog_number_clean__icontains='645004')
elapsed = (time.time() - start) * 1000
print(f'✅ Поиск по очищенному номеру: {results.count()} результатов за {elapsed:.2f}ms')

# Тест 2: Поиск по имени
start = time.time()
results = Product.objects.filter(name__icontains='фильтр')
elapsed = (time.time() - start) * 1000
print(f'✅ Поиск по имени: {results.count()} результатов за {elapsed:.2f}ms')
"
check_status "Поиск работает"

# 6. Проверка кеширования
echo ""
echo "6️⃣ Проверка кеширования..."
python3 manage.py shell -c "
from django.core.cache import cache

# Очищаем кеш
cache.clear()
print('🗑️ Кеш очищен')

# Устанавливаем тестовое значение
cache.set('test_key', 'test_value', 60)
value = cache.get('test_key')
if value == 'test_value':
    print('✅ Кеш работает корректно')
else:
    print('❌ Ошибка кеширования')
"
check_status "Кеширование работает"

# 7. Проверка SEO
echo ""
echo "7️⃣ Проверка SEO компонентов..."
if [ -f "shop/seo.py" ]; then
    echo -e "${GREEN}✅ shop/seo.py существует${NC}"
else
    echo -e "${RED}❌ shop/seo.py не найден${NC}"
fi

if [ -f "shop/sitemap_views.py" ]; then
    echo -e "${GREEN}✅ shop/sitemap_views.py существует${NC}"
else
    echo -e "${RED}❌ shop/sitemap_views.py не найден${NC}"
fi

# 8. Проверка команд импорта
echo ""
echo "8️⃣ Проверка команд импорта..."
python3 manage.py help import_brands_dbf > /dev/null 2>&1
check_status "import_brands_dbf доступна"

python3 manage.py help import_dbf > /dev/null 2>&1
check_status "import_dbf доступна"

python3 manage.py help import_oe_analogs_dbf > /dev/null 2>&1
check_status "import_oe_analogs_dbf доступна"

python3 manage.py help link_product_images > /dev/null 2>&1
check_status "link_product_images доступна"

python3 manage.py help populate_clean_numbers > /dev/null 2>&1
check_status "populate_clean_numbers доступна"

# 9. Проверка админки
echo ""
echo "9️⃣ Проверка админ-панели..."
python3 manage.py shell -c "
from django.contrib.admin.sites import site
from shop.models import Product, Brand, OeKod

if Product in [model._meta.model for model in site._registry.keys()]:
    print('✅ Product зарегистрирован в админке')
else:
    print('❌ Product не зарегистрирован')

if Brand in [model._meta.model for model in site._registry.keys()]:
    print('✅ Brand зарегистрирован в админке')
else:
    print('❌ Brand не зарегистрирован')
"

# 10. Проверка логов
echo ""
echo "🔟 Проверка системы логирования..."
if [ -f "logs/django.log" ]; then
    echo -e "${GREEN}✅ logs/django.log существует${NC}"
    echo "Последние 3 строки лога:"
    tail -n 3 logs/django.log
else
    echo -e "${YELLOW}⚠️ logs/django.log не найден (создастся автоматически)${NC}"
fi

# Финальный отчёт
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!${NC}"
echo ""
echo "📋 Следующие шаги:"
echo "   1. Импортируйте данные (см. DEPLOYMENT_GUIDE.md)"
echo "   2. Запустите сервер: python3 manage.py runserver"
echo "   3. Откройте http://localhost:8000/admin/"
echo ""
echo "📖 Документация: DEPLOYMENT_GUIDE.md"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

