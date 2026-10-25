# MuGuard backend for Railway. Build context is the repo root, like the web service:
#   docker build -f backend/Dockerfile .
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv PYTHONUNBUFFERED=1

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/samples ./samples

# Only reachable over Railway's private network (through the web service), so forwarded
# headers come from our Caddy, which sets X-Forwarded-For from Railway's X-Real-IP.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn app.main:app --host :: --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
