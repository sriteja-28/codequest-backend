# CodeQuest backend — Django ASGI (HTTP + WebSocket) behind a reverse proxy.
#
# Build:  docker build -t codequest-backend backend
# Run:    uvicorn config.asgi:application (compose sets
#         DJANGO_SETTINGS_MODULE=config.settings.production and the env file)
#
# The migrate/collectstatic step runs in a separate one-shot compose service
# (infra/docker-compose.prod.yml "migrate") so concurrent workers never race;
# this image only serves.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

WORKDIR /app

# Dependencies first so code edits don't reinstall them.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# uid 10001, no shell. staticfiles/ is a mounted volume (filled by the migrate
# service, served by Caddy); media/ is unused today but reserved.
RUN useradd -r -s /usr/sbin/nologin -u 10001 codequest \
    && mkdir -p staticfiles media \
    && chown -R codequest:codequest /app

USER codequest
EXPOSE 8000

# Healthcheck presents the first ALLOWED_HOSTS as the Host header — Django
# rejects requests with foreign Host headers (DisallowedHost), and a plain
# 127.0.0.1 request would 400 and never pass.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request; h=(os.environ.get('ALLOWED_HOSTS') or 'localhost').split(',')[0].strip(); r=urllib.request.Request('http://127.0.0.1:8000/api/health/', headers={'Host': h}); urllib.request.urlopen(r, timeout=4)"]

# --proxy-headers: trust X-Forwarded-* from the reverse proxy (client IP for
# throttling, X-Forwarded-Proto for Django's SECURE_PROXY_SSL_HEADER).
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]
