#!/bin/bash
# 🧹 УДАЛЕНИЕ ДУБЛИКАТОВ - Автоматический скрипт

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   🧹 ЗАПУСК УДАЛЕНИЯ ДУБЛИКАТОВ                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# 1. Подключение к серверу и запуск удаления
echo "📡 Подключаюсь к серверу..."
ssh root@45.130.42.65 << 'ENDSSH'

echo "📂 Перехожу в директорию проекта..."
cd "/root/tir-lugansk 12.02.26"

echo "🔧 Активирую окружение..."
source venv/bin/activate

echo ""
echo "🗑️  ЗАПУСК УДАЛЕНИЯ ДУБЛИКАТОВ..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 remove_duplicates.py

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔄 Перезапускаю Django..."

# Останавливаем Django
PID=$(ps aux | grep "[m]anage.py runserver" | awk '{print $2}')
if [ ! -z "$PID" ]; then
  kill -9 $PID
  echo "   ✅ Django остановлен (PID: $PID)"
else
  echo "   ⚠️  Django уже остановлен"
fi

# Запускаем Django
nohup python3 manage.py runserver 0.0.0.0:8000 > /dev/null 2>&1 &
sleep 2

# Проверяем что запустился
NEW_PID=$(ps aux | grep "[m]anage.py runserver" | awk '{print $2}')
if [ ! -z "$NEW_PID" ]; then
  echo "   ✅ Django запущен (PID: $NEW_PID)"
else
  echo "   ❌ Ошибка запуска Django!"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 ФИНАЛЬНАЯ ПРОВЕРКА:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 manage.py shell -c "
from shop.models import Product
total = Product.objects.count()
with_dup = Product.objects.filter(tmp_id__icontains='-dup').count()
print(f'✅ Всего товаров:  {total:,}')
print(f'🎯 Ожидалось:      198,538')
print(f'📊 Разница:        {abs(total - 198538):,}')
print(f'🔴 С -dup:         {with_dup}')
print('')
if with_dup == 0 and abs(total - 198538) < 1000:
    print('✅✅✅ ОТЛИЧНО! ДУБЛИКАТЫ УДАЛЕНЫ! ✅✅✅')
elif with_dup == 0:
    print('✅ Дубликаты удалены, но количество отличается от ожидаемого')
else:
    print(f'⚠️  Осталось {with_dup} товаров с -dup')
"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 ПРОВЕРЬТЕ НА ФРОНТЕ:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "   http://new.tir-lugansk.ru/shop/catalog/"
echo "   Должно показать: ~198,538 товаров"
echo ""
echo "   http://new.tir-lugansk.ru/shop/catalog/?search=16351024"
echo "   Дубликаты должны исчезнуть"
echo ""
echo "✅ ГОТОВО!"
echo ""

ENDSSH

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   ✅ СКРИПТ ЗАВЕРШЕН                                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"

