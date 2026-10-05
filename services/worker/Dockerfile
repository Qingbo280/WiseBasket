FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
COPY services/worker/requirements-worker.txt ./services/worker/requirements-worker.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt -r services/worker/requirements-worker.txt
COPY scripts ./scripts
COPY packages ./packages
# Receipt tasks import the API's extraction service, database models, settings,
# and cloud gateway. Keep the complete package in the worker image so queued
# and inline extraction run the same code.
COPY services/api ./services/api
CMD ["/bin/sh", "-c", "exec celery -A scripts.celery_worker:celery_app worker --loglevel=INFO --concurrency=${CELERY_WORKER_CONCURRENCY:-1} --prefetch-multiplier=1 --beat --scheduler celery.beat:PersistentScheduler --schedule-filename /tmp/celerybeat-schedule"]
