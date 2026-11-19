#!/usr/bin/env bash
# Nightly database backup. Keeps the last 14 days.
# Cron example (runs at 02:30):
#   30 2 * * * cd /srv/clinic-booking-platform && ./scripts/backup.sh >> backups/backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p backups
# shellcheck disable=SC1091
source .env

FILE="backups/booking-$(date +%F-%H%M).sql.gz"
docker compose -f compose.prod.yml exec -T db \
  pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --no-owner \
  | gzip > "$FILE"

find backups -name 'booking-*.sql.gz' -mtime +14 -delete
echo "$(date): saved $FILE"

# restore with:
#   gunzip -c backups/<file>.sql.gz | docker compose -f compose.prod.yml exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
