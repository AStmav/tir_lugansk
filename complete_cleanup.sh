#!/bin/bash
# complete_cleanup.sh - Полный цикл очистки дубликатов через локальную БД

set -e  # Остановить при ошибке

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   🔄 УДАЛЕНИЕ ДУБЛИКАТОВ ЧЕРЕЗ ЛОКАЛЬНУЮ БД                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

LOCAL_DIR="/Users/ast_mav/Documents/For_work/tir-lugansk 12.02.26"
SERVER_DIR="/root/tir-lugansk 12.02.26"
SERVER="root@45.130.42.65"

cd "$LOCAL_DIR"

# ШАГ 1: Скачать БД с сервера
echo "📥 Шаг 1/5: Скачиваем БД с сервера..."
echo "   Создаю локальный бэкап..."
cp db.sqlite3 db.sqlite3.local_backup 2>/dev/null && echo "   ✅ Локальный бэкап создан" || echo "   ℹ️  Локальной БД не было"

echo "   Скачиваю БД с сервера..."
scp "$SERVER:$SERVER_DIR/db.sqlite3" ./db.sqlite3
SIZE=$(ls -lh db.sqlite3 | awk '{print $5}')
echo "   ✅ Скачано: $SIZE"

# ШАГ 2: Активировать окружение и проверить
echo ""
echo "📊 Шаг 2/5: Проверяем текущее состояние..."
source venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null || {
    echo "   ❌ Не найдено виртуальное окружение venv или .venv"
    exit 1
}

python3 manage.py shell -c "
from shop.models import Product
total = Product.objects.count()
with_dup = Product.objects.filter(tmp_id__icontains='-dup').count()
without_dup = total - with_dup
print(f'   📊 Всего товаров:   {total:,}')
print(f'   🔴 С -dup:          {with_dup:,} ({with_dup/total*100:.1f}%)')
print(f'   ✅ Без -dup:        {without_dup:,} ({without_dup/total*100:.1f}%)')
print(f'   🎯 Ожидается:       198,538')
"

# ШАГ 3: Удалить дубликаты
echo ""
echo "🗑️  Шаг 3/5: Удаляем дубликаты..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 remove_duplicates.py
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ШАГ 4: Проверить результат
echo ""
echo "✅ Шаг 4/5: Проверяем результат..."
python3 manage.py shell -c "
from shop.models import Product
total = Product.objects.count()
with_dup = Product.objects.filter(tmp_id__icontains='-dup').count()
expected = 198538
diff = abs(total - expected)
diff_percent = (diff / expected * 100)

print(f'   📊 Всего товаров:   {total:,}')
print(f'   🔴 С -dup:          {with_dup}')
print(f'   🎯 Ожидалось:       {expected:,}')
print(f'   📈 Разница:         {diff:,} ({diff_percent:.2f}%)')
print('')

if with_dup == 0 and diff_percent < 1:
    print('   ✅✅✅ ОТЛИЧНО! Дубликаты удалены, количество точное! ✅✅✅')
    exit(0)
elif with_dup == 0:
    print('   ✅ Дубликаты удалены!')
    print(f'   ⚠️  Но разница с ожидаемым: {diff:,} товаров')
    exit(0)
else:
    print(f'   ⚠️  ВНИМАНИЕ: Осталось {with_dup} товаров с -dup!')
    exit(1)
" && CLEANUP_SUCCESS=true || CLEANUP_SUCCESS=false

if [ "$CLEANUP_SUCCESS" = false ]; then
    echo ""
    echo "❌ Удаление дубликатов завершилось с ошибкой!"
    echo "   Проверьте вывод выше"
    exit 1
fi

# ШАГ 5: Подтверждение загрузки на сервер
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📤 Шаг 5/5: Загрузка на сервер"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "Загрузить очищенную БД на сервер? (y/n): " confirm

if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    echo ""
    echo "   🛑 Останавливаю Django на сервере..."
    ssh "$SERVER" "ps aux | grep '[m]anage.py runserver' | awk '{print \$2}' | xargs kill -9 2>/dev/null || true"
    sleep 1
    echo "      ✅ Django остановлен"
    
    echo ""
    echo "   💾 Создаю бэкап на сервере..."
    BACKUP_NAME="db.sqlite3.backup_$(date +%Y%m%d_%H%M%S)"
    ssh "$SERVER" "cd '$SERVER_DIR' && cp db.sqlite3 '$BACKUP_NAME'"
    echo "      ✅ Бэкап создан: $BACKUP_NAME"
    
    echo ""
    echo "   📤 Загружаю очищенную БД..."
    scp ./db.sqlite3 "$SERVER:$SERVER_DIR/db.sqlite3"
    echo "      ✅ БД загружена"
    
    echo ""
    echo "   🚀 Запускаю Django..."
    ssh "$SERVER" "cd '$SERVER_DIR' && source venv/bin/activate && nohup python3 manage.py runserver 0.0.0.0:8000 > /dev/null 2>&1 &"
    sleep 3
    
    echo "   ✅ Проверяю статус..."
    ssh "$SERVER" "ps aux | grep '[m]anage.py runserver'" && echo "      ✅ Django запущен" || echo "      ❌ Ошибка запуска"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅✅✅ ГОТОВО! ✅✅✅"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "🌐 ПРОВЕРЬТЕ НА ФРОНТЕ:"
    echo "   http://new.tir-lugansk.ru/shop/catalog/"
    echo "   Должно показать: ~198,538 товаров"
    echo ""
    echo "   http://new.tir-lugansk.ru/shop/catalog/?search=16351024"
    echo "   Дубликаты должны исчезнуть"
    echo ""
else
    echo ""
    echo "❌ Загрузка на сервер отменена"
    echo ""
    echo "   Очищенная БД сохранена локально: db.sqlite3"
    echo "   Размер: $(ls -lh db.sqlite3 | awk '{print $5}')"
    echo ""
    echo "   📝 Для загрузки вручную позже:"
    echo "   1. Остановите Django:"
    echo "      ssh $SERVER \"ps aux | grep '[m]anage.py' | awk '{print \\\$2}' | xargs kill -9\""
    echo ""
    echo "   2. Создайте бэкап:"
    echo "      ssh $SERVER \"cd '$SERVER_DIR' && cp db.sqlite3 db.sqlite3.backup\""
    echo ""
    echo "   3. Загрузите БД:"
    echo "      scp ./db.sqlite3 $SERVER:$SERVER_DIR/db.sqlite3"
    echo ""
    echo "   4. Запустите Django:"
    echo "      ssh $SERVER \"cd '$SERVER_DIR' && nohup python3 manage.py runserver 0.0.0.0:8000 &\""
    echo ""
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   ✅ СКРИПТ ЗАВЕРШЕН                                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"

