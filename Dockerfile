# syntax=docker/dockerfile:1

FROM python:3.14.7-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.5

# Deps-only layer first so code changes don't invalidate the dependency cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY warden ./warden
COPY main.py ./
RUN uv sync --frozen --no-dev

FROM python:3.14.7-slim AS runtime

ENV TZ=Asia/Jakarta \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin warden

WORKDIR /app
COPY --from=builder --chown=warden:warden /app/.venv ./.venv
COPY --from=builder --chown=warden:warden /app/warden ./warden
COPY --from=builder --chown=warden:warden /app/main.py ./

USER warden
ENTRYPOINT ["python", "main.py"]
