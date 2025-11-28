FROM python:3.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for science/ffmpeg/faiss builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first (cached layer)
RUN pip install --upgrade pip

# Copy only requirements first for better layer caching
# This layer will be cached unless requirements.txt changes
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy application code (this invalidates cache only when code changes)
COPY . .

ENV PYTHONPATH=/app

# Cloud Run provides the listening port via the PORT env var (default 8080).
# We respect that here so the container starts correctly on the platform.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8080}"]

