#!/bin/sh
# Runs before the main command in every container.
set -e

# wait until Postgres accepts connections (up to ~60s)
python - <<'PY'
import os, sys, time
import psycopg

for attempt in range(30):
    try:
        psycopg.connect(
            dbname=os.environ.get("POSTGRES_DB", "booking"),
            user=os.environ.get("POSTGRES_USER", "booking"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            host=os.environ.get("POSTGRES_HOST", "db"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            connect_timeout=2,
        ).close()
        sys.exit(0)
    except psycopg.OperationalError:
        print("Waiting for the database...", flush=True)
        time.sleep(2)
sys.exit("Database not reachable")
PY

# only the web container sets these, so the worker and beat don't race it
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi
if [ "${COLLECTSTATIC:-0}" = "1" ]; then
  python manage.py collectstatic --noinput
fi
if [ "${SEED_DEMO:-0}" = "1" ]; then
  python manage.py seed_demo --admin --demo-bookings "${DEMO_BOOKINGS:-120}"
fi

exec "$@"
