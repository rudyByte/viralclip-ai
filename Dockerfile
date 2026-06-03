# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV HF_HOME=/app/models
ENV APP_PORT=7860
ENV APP_HOST=0.0.0.0
ENV DATABASE_URL=sqlite+aiosqlite:////app/data/viralclip.db
ENV TEMP_DIR=/app/temp
ENV EXPORT_DIR=/app/exports
ENV ASSETS_DIR=/app/assets
ENV MODELS_DIR=/app/models

# Set working directory inside container
WORKDIR /app

# Install system dependencies (ffmpeg is essential, plus opencv/moviepy dependencies, and nodejs for yt-dlp signature deciphering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set up user 1000 for Hugging Face Spaces non-root compliance
RUN useradd -m -u 1000 user
RUN mkdir -p /app/data /app/temp /app/exports /app/assets /app/models \
    && chown -R user:user /app

# Copy requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=user:user . /app/

# Switch to the non-root user
USER user

# Expose backend port for HF (defaults to 7860)
EXPOSE 7860

# Start uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--log-level", "info"]
