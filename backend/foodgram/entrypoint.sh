#!/bin/sh
set -e



python manage.py migrate --noinput
python manage.py collectstatic --noinput
cp -r collected_static/. /backend_static/static/
exec gunicorn --bind 0.0.0.0:8000 foodgram.wsgi