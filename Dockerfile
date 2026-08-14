# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS web-builder
WORKDIR /src
RUN corepack enable && corepack prepare pnpm@11.3.0 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/brand/package.json packages/brand/package.json
COPY packages/design/package.json packages/design/package.json
COPY packages/graph/package.json packages/graph/package.json
COPY packages/ui/package.json packages/ui/package.json
RUN pnpm install --filter @hawkeye/web... --frozen-lockfile
COPY apps/web apps/web
COPY packages packages
RUN pnpm --filter @hawkeye/web build

FROM ghcr.io/astral-sh/uv:0.11.2 AS uv

FROM python:3.12-slim-bookworm AS wheel-builder
COPY --from=uv /uv /uvx /bin/
WORKDIR /src
COPY pyproject.toml uv.lock README.md ./
COPY apps/api apps/api
COPY evaluation/fixtures/controlled-interactions-v1.json evaluation/fixtures/controlled-interactions-v1.json
COPY --from=web-builder /src/apps/api/src/hawkeye/review_app/static apps/api/src/hawkeye/review_app/static
RUN uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file /tmp/requirements.txt \
    && uv build --wheel

FROM mcr.microsoft.com/playwright/python:v1.50.0-noble AS runtime
ENV HAWKEYE_CONTAINER=1 \
    HAWKEYE_DATA_DIR=/data \
    HAWKEYE_PORT=8760 \
    PYTHONUNBUFFERED=1

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
COPY --from=wheel-builder /src/dist/*.whl /tmp/
COPY --from=wheel-builder /tmp/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
    && python -m pip install --no-cache-dir --no-deps /tmp/*.whl \
    && rm -f /tmp/*.whl \
    && rm -f /tmp/requirements.txt \
    && mkdir -p /data \
    && chown -R pwuser:pwuser /data

USER pwuser
WORKDIR /app
EXPOSE 8760
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8760/health', timeout=2).read()"
ENTRYPOINT ["hawkeye-container"]
