FROM python:3.13.7-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home app
RUN chown app:app /app
COPY --chown=app:app . .
USER app
RUN DJANGO_DEBUG=1 DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["gunicorn", "--config", "deploy/gunicorn_config.py", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "40", "--access-logfile", "-", "--access-logformat", "%(m)s %(s)s %(L)s %(b)s", "--error-logfile", "-"]
