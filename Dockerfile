# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Build stage to install deps
FROM base AS deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
# Install runtime deps only for smaller image
RUN pip install --upgrade pip && \
    pip install --no-cache-dir fastapi==0.111.0 "uvicorn[standard]"==0.30.0 pydantic==2.8.2 structlog==24.1.0

# Final runtime
FROM base AS runtime
ENV APP_ENV=prod \
    APP_VERSION=0.1.0
COPY --from=deps /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=deps /usr/local/bin /usr/local/bin
COPY src ./src
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

