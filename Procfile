web: gunicorn loyalty_platform.wsgi:application
worker: celery -A loyalty_platform worker --loglevel=info
