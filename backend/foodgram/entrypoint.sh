#!/bin/sh
set -e



python manage.py migrate --noinput
python manage.py collectstatic --noinput
cp -r collected_static/. /backend_static/static/
exec daphne -b 0.0.0.0 -p 8000 foodgram.asgi:application