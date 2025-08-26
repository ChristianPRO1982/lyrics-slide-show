#!/bin/sh
# Waits for MySQL using mysqladmin ping with credentials (works with MySQL 8).

echo "Waiting for MySQL..."

DB_HOST="${DOCKER_MYSQL_HOST:-${DB_HOST:-db}}"
DB_PORT="${DOCKER_MYSQL_PORT:-${DB_PORT:-3306}}"
DB_USER="${DOCKER_MYSQL_USER:-root}"
DB_PASS="${DOCKER_MYSQL_PASSWORD:-${DOCKER_MYSQL_ROOT_PASSWORD:-}}"
ATTEMPTS="${DB_WAIT_ATTEMPTS:-60}"
DELAY="${DB_WAIT_DELAY:-2}"

export MYSQL_PWD="$DB_PASS"

i=1
while [ "$i" -le "$ATTEMPTS" ]; do
  if mysqladmin ping --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" --protocol=TCP --silent; then
    echo "MySQL is ready!"
    exit 0
  fi
  echo "Attempt ${i}/${ATTEMPTS}: waiting for ${DB_HOST}:${DB_PORT}..."
  i=$((i+1))
  sleep "$DELAY"
done

echo "MySQL not reachable after ${ATTEMPTS} attempts."
exit 1
