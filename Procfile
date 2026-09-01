web: gunicorn stalwart_project.wsgi:application --workers 2 --timeout 120
release: python manage.py migrate --noinput && python manage.py setup_roles && python manage.py collectstatic --noinput
