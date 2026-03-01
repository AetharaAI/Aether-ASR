# ASR Worker Dockerfile with GPU support
FROM nvidia/cuda:12.1.1-devel-ubuntu22.04 as base

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3-pip \
    python3.11-dev \
    build-essential \
    libffi-dev \
    ffmpeg \
    libsndfile1 \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1
RUN update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Builder stage for Python dependencies
FROM base as builder

WORKDIR /build

# Install build dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create models directory
RUN mkdir -p /models
ENV WHISPER_MODELS_DIR=/models

# Final stage
FROM base as production

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/dist-packages /usr/local/lib/python3.11/dist-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /models /models

# Set environment variables
ENV PYTHONPATH=/app
ENV WHISPER_MODELS_DIR=/models
ENV CUDA_VISIBLE_DEVICES=0

# Create non-root user
RUN groupadd -r asr && useradd -r -g asr asr

# Set working directory
WORKDIR /app

# Copy application code
COPY app/ ./app/

# Set ownership
RUN chown -R asr:asr /app

# Switch to non-root user
USER asr

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "from app.celery_app import app; print('Worker healthy')" || exit 1

# Run Celery worker
CMD ["celery", "-A", "app.celery_app", "worker", "--loglevel=info", "--queues=transcription,webhook", "--concurrency=1"]
