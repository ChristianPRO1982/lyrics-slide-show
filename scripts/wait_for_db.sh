#!/bin/sh
# Waits for PostgreSQL or MySQL depending on DB_ENGINE.

DB_ENGINE="${DB_ENGINE:-django.db.backends.mysql}"
ATTEMPTS="${DB_WAIT_ATTEMPTS:-60}"
DELAY="${DB_WAIT_DELAY:-2}"

wait_postgres() {
  echo "Waiting for PostgreSQL..."
  DB_HOST="${DB_FUNCTIONAL_HOST:-${DB_HOST:-postgres}}"
  DB_PORT="${DB_PORT:-5432}"
  DB_USER="${DB_FUNCTIONAL_USER:-${DB_USER:-postgres}}"

  i=1
  while [ "$i" -le "$ATTEMPTS" ]; do
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
      echo "PostgreSQL is ready!"
      exit 0
    fi
    echo "Attempt ${i}/${ATTEMPTS}: waiting for ${DB_HOST}:${DB_PORT}..."
    i=$((i+1))
    sleep "$DELAY"
  done

  echo "PostgreSQL not reachable after ${ATTEMPTS} attempts."
  exit 1
}

wait_mysql() {
  echo "Waiting for MySQL..."

  DB_HOST="${DOCKER_MYSQL_HOST:-${DB_HOST:-db}}"
  DB_PORT="${DOCKER_MYSQL_PORT:-${DB_PORT:-3306}}"
  DB_USER="${DOCKER_MYSQL_USER:-root}"
  DB_PASS="${DOCKER_MYSQL_PASSWORD:-${DOCKER_MYSQL_ROOT_PASSWORD:-}}"

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
}

case "$DB_ENGINE" in
  *postgresql*)
    wait_postgres
    ;;
  *)
    wait_mysql
    ;;
esac
