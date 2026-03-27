#!/usr/bin/env bash
# Экспорт данных из текущей БД Django (PostgreSQL) в JSON.
# Запуск из корня проекта или: ./scripts/dumpdata_for_postgres.sh
# Результат: data_backup.json в корне проекта.

set -e
cd "$(dirname "$0")/.."
BACKUP_FILE="${1:-data_backup.json}"
echo "Экспорт в $BACKUP_FILE ..."
python manage.py dumpdata --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.Permission \
  -o "$BACKUP_FILE"
echo "Готово. Размер: $(ls -lh "$BACKUP_FILE" | awk '{print $5}')"
