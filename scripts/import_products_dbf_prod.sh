#!/usr/bin/env bash
# Импорт номенклатуры из DBF 1С на продакшене (команда import_dbf).
#
# Запуск на сервере из корня проекта:
#   ./scripts/import_products_dbf_prod.sh /var/www/tir-lugansk/incoming_images/1C060826.DBF
#
# Тест на 100 строк (без записи в фон):
#   TEST_RECORDS=100 ./scripts/import_products_dbf_prod.sh /path/to/file.DBF
#
# Режим обновления (по умолчанию update):
#   UPDATE_MODE=skip ./scripts/import_products_dbf_prod.sh /path/to/file.DBF
#
# Переменные:
#   UPDATE_MODE   — update | skip | create_only  (default: update)
#   BATCH_SIZE    — default: 10000
#   TEST_RECORDS  — если >0, импорт только первых N записей
#   BACKGROUND=1  — запись в logs/ и nohup (для ~200k строк)

set -euo pipefail

cd "$(dirname "$0")/.."

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-tir_lugansk.settings_prod}"

DBF_FILE="${1:-}"
UPDATE_MODE="${UPDATE_MODE:-update}"
BATCH_SIZE="${BATCH_SIZE:-10000}"
TEST_RECORDS="${TEST_RECORDS:-0}"
BACKGROUND="${BACKGROUND:-1}"

if [[ -z "$DBF_FILE" ]]; then
  echo "Использование: $0 /path/to/1C060826.DBF"
  echo ""
  echo "Пример загрузки файла с локального Mac на сервер:"
  echo "  scp ~/Downloads/1C060826.DBF root@45.130.42.65:/var/www/tir-lugansk/incoming_images/"
  exit 1
fi

if [[ ! -f "$DBF_FILE" ]]; then
  echo "Ошибка: файл не найден: $DBF_FILE"
  exit 1
fi

if [[ ! -x venv/bin/python ]]; then
  echo "Ошибка: не найден venv/bin/python (запускайте из корня проекта на сервере)"
  exit 1
fi

mkdir -p logs

PYTHON=venv/bin/python
BASE_NAME="$(basename "$DBF_FILE" .DBF)"
BASE_NAME="$(basename "$BASE_NAME" .dbf)"
LOG_FILE="logs/import_dbf_${BASE_NAME}_$(date +%Y%m%d_%H%M%S).log"

CMD=(
  "$PYTHON" manage.py import_dbf "$DBF_FILE"
  --batch-size "$BATCH_SIZE"
  --disable-transactions
  --update-mode "$UPDATE_MODE"
  --encoding cp1251
)

if [[ "$TEST_RECORDS" -gt 0 ]]; then
  CMD+=(--test-records "$TEST_RECORDS")
  BACKGROUND=0
fi

echo "Файл:        $DBF_FILE"
echo "Размер:      $(ls -lh "$DBF_FILE" | awk '{print $5}')"
echo "Режим:       $UPDATE_MODE"
echo "Batch:       $BATCH_SIZE"
echo "Settings:    $DJANGO_SETTINGS_MODULE"
echo "Лог:         $LOG_FILE"

if [[ "$BACKGROUND" == "1" ]]; then
  echo ""
  echo "Запуск в фоне (nohup). Прогресс: tail -f $LOG_FILE"
  nohup "${CMD[@]}" >> "$LOG_FILE" 2>&1 &
  echo "PID: $!"
else
  echo ""
  echo "Запуск в текущей сессии..."
  "${CMD[@]}" 2>&1 | tee "$LOG_FILE"
fi
