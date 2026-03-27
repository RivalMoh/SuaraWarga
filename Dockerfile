FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System packages required for audio processing.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first to improve build cache reuse.
COPY requirements.txt requirements-audio.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-audio.txt

# Copy application code.
COPY . .

# Ensure volume mount target exists for SQLite persistence.
RUN mkdir -p /data

EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
