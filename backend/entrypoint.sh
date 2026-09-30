#!/bin/sh

DB_HOST="${DB_HOST:-mysql-service}"
DB_PORT="${DB_PORT:-3306}"
export DB_HOST DB_PORT

echo "Waiting for MySQL at $DB_HOST:$DB_PORT..."

until python -c "import socket; socket.create_connection(('$DB_HOST', int('$DB_PORT')), 2)" 2>/dev/null
do
    echo "MySQL is not ready yet. Waiting..."
    sleep 2
done

echo "MySQL is available!"

python manage.py migrate
python manage.py check --database default

echo "Starting Django..."

exec python manage.py runserver 0.0.0.0:8000
