#!/bin/sh
echo "Waiting for MySQL..."

while ! mysqladmin ping -h"db" --silent; do
    sleep 1
done

echo "MySQL is ready!"

exec "$@"
