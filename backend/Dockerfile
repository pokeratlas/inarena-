FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    INARENA_DB_PATH=/var/lib/inarena/inarena.sqlite3

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY app /app/app

RUN python -m pip install --upgrade pip \
    && pip install ".[postgres]" \
    && useradd --create-home --uid 10001 inarena \
    && mkdir -p /var/lib/inarena \
    && chown -R inarena:inarena /var/lib/inarena

USER inarena

VOLUME ["/var/lib/inarena"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
