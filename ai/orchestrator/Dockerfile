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

# Expose port
EXPOSE 8040

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8040"]

