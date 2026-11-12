# syntax=docker/dockerfile:1
#
# Single image running both the Telegram bot and the admin dashboard (see
# app.py) in one container/process.

# ---- builder: install dependencies into an isolated prefix ----
FROM python:3.12-slim AS builder

WORKDIR /install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/deps -r requirements.txt

# ---- runtime: slim image with only what's needed to run ----
FROM python:3.12-slim

RUN groupadd -r urlwarden && useradd -r -g urlwarden -m -s /usr/sbin/nologin urlwarden

WORKDIR /app

COPY --from=builder /install/deps /usr/local
COPY common ./common
COPY bot ./bot
COPY dashboard ./dashboard
COPY app.py ./app.py

RUN mkdir -p /app/data && chown -R urlwarden:urlwarden /app

USER urlwarden

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')" || exit 1

CMD ["python", "app.py"]
