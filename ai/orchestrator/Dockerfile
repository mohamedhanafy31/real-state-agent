FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including ffmpeg for audio processing)
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create logs directory
RUN mkdir -p logs

# Cloud Run provides the listening port via the PORT env var (default 8080).
# We respect that here so the container starts correctly on the platform.
ENV PORT=8080
EXPOSE 8080

# Run the application using Python wrapper that reads PORT env var
CMD ["python", "app/start.py"]

