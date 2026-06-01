# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
# Cache HuggingFace models in the mapped Docker volume
ENV HF_HOME=/app/models

# Set working directory inside container
WORKDIR /app

# Install system dependencies (ffmpeg is essential, plus opencv/moviepy dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . /app/

# Expose backend port
EXPOSE 8000

# Start uvicorn directly — NO reload to prevent watchfiles killing running pipeline jobs
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
