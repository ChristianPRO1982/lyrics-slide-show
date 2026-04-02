#!/bin/sh

set -eu

python manage.py collectstatic --noinput

exec gunicorn lyrics_slide_show.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --access-logfile - \
  --error-logfile -
