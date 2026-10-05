FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY services ./services
COPY packages ./packages
COPY data/samples ./data/samples
CMD ["/bin/sh", "-c", "exec uvicorn services.api.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
