# One image runs the website, the Celery worker and Celery beat.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# run as a normal user, not root
RUN groupadd --system app && useradd --system --gid app --home-dir /app app

# dev builds pass REQUIREMENTS=requirements-dev.txt to get pytest and ruff
ARG REQUIREMENTS=requirements.txt
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r ${REQUIREMENTS}

COPY --chown=app:app . .
RUN mkdir -p /app/staticfiles && chown app:app /app/staticfiles

USER app

EXPOSE 8000
ENTRYPOINT ["sh", "docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
