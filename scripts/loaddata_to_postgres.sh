#!/usr/bin/env bash
# Загрузка данных из data_backup.json в текущую БД.
# Перед запуском: переключить проект на PostgreSQL (DJANGO_SETTINGS_MODULE и DB_* в .env),
# выполнить: python manage.py migrate
# Запуск из корня проекта.

set -e
cd "$(dirname "$0")/.."
DATA_FILE="${1:-data_backup.json}"
if [[ ! -f "$DATA_FILE" ]]; then
  echo "Файл $DATA_FILE не найден."
  exit 1
fi
echo "Загрузка из $DATA_FILE в текущую БД ..."
python manage.py loaddata "$DATA_FILE"
echo "Готово. При необходимости сбросьте последовательности: python manage.py sqlsequencereset shop pages auth | python manage.py dbshell"
