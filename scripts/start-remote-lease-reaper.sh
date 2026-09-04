#!/bin/sh

set -u

while true; do
  python manage.py purge_remote_connections || true
  sleep "${REMOTE_CONNECTION_HEARTBEAT_SECONDS:-5}"
done
