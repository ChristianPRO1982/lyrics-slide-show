#!/bin/sh

set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec daphne \
  --bind 0.0.0.0 \
  --port 8000 \
  --proxy-headers \
  lyrics_slide_show.asgi:application
