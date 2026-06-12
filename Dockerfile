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
ENV RUNNING_IN_DOCKER=true
ENV YT_DLP_COOKIES_FILE=/app/data/cookies.txt
ENV YT_DLP_PO_TOKEN_FILE=/app/data/po_token.txt

# Set working directory inside container
WORKDIR /app

# Install system dependencies (ffmpeg is essential, plus opencv/moviepy dependencies, and libcurl for curl-cffi)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    nodejs \
    libcurl4-openssl-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up user 1000 for Hugging Face Spaces non-root compliance
RUN useradd -m -u 1000 user
RUN mkdir -p /app/data /app/temp /app/exports /app/assets /app/models \
    && chown -R user:user /app

# Copy requirements
COPY requirements.txt /app/
# Upgrade pip, install requirements, then force latest yt-dlp + curl-cffi + certifi
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --upgrade -r requirements.txt && \
    pip install --no-cache-dir --upgrade yt-dlp curl-cffi certifi && \
    echo "=== Package versions ===" && \
    python -c "import yt_dlp; print('yt-dlp:', yt_dlp.version.__version__)" && \
    python -c "import certifi; print('certifi:', certifi.__version__ if hasattr(certifi, '__version__') else 'ok')" && \
    python -c "import curl_cffi; print('curl-cffi:', curl_cffi.__version__ if hasattr(curl_cffi, '__version__') else 'ok')" && \
    echo "========================"

# Copy application source code
COPY --chown=user:user . /app/

# Seed server cookies for HF fallback — the repo ships valid YouTube cookies in backend/
RUN if [ -f /app/backend/cookies.txt ]; then \
      cp /app/backend/cookies.txt /app/data/cookies.txt && \
      chown user:user /app/data/cookies.txt && \
      echo "Cookies seeded from backend/cookies.txt to /app/data/cookies.txt" ; \
    elif [ -f /app/cookies.txt ]; then \
      cp /app/cookies.txt /app/data/cookies.txt && \
      chown user:user /app/data/cookies.txt && \
      echo "Cookies seeded from /app/cookies.txt to /app/data/cookies.txt" ; \
    else \
      echo "WARNING: No cookies.txt found — HF Space may struggle with YouTube downloads" ; \
    fi ; \
    # Also copy to /data/ (HF persistent volume) so cookies survive restarts
    if [ -f /app/data/cookies.txt ] && [ -d /data ]; then \
      cp /app/data/cookies.txt /data/cookies.txt && \
      chown user:user /data/cookies.txt && \
      echo "Also seeded to /data/cookies.txt (HF persistent volume)" ; \
    fi

# Switch to the non-root user
USER user

# Expose backend port for HF (defaults to 7860)
EXPOSE 7860

# Start uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--log-level", "info"]
