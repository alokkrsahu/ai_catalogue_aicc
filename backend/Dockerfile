# Dockerfile for Django backend
# CRITICAL FIX: Use stable Debian Bookworm instead of Trixie (testing) for better network reliability
FROM python:3.13-slim-bookworm

WORKDIR /app

# CRITICAL FIX: Install system dependencies with robust retry logic and error handling
# Split into essential and optional packages - continue even if optional packages fail
RUN set -eux; \
    # Retry apt-get update up to 3 times with delays
    for i in 1 2 3; do \
        apt-get update --fix-missing && break || (echo "Retry $i failed, waiting..." && sleep 10); \
    done && \
    # Install essential network and build tools first (must succeed)
    apt-get install -y --no-install-recommends \
        curl \
        wget \
        ca-certificates \
        gnupg2 \
        build-essential \
        python3-dev \
        libpq-dev \
        pkg-config \
        git \
    && \
    # Install essential document processing libraries (must succeed)
    apt-get install -y --no-install-recommends \
        libxml2-dev \
        libxslt1-dev \
        libjpeg-dev \
        libmagic1 \
    && \
    # Install document processing tools (retry on failure, but continue)
    (apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        antiword \
        unrtf \
    || (echo "Warning: Some document tools failed, retrying..." && \
        sleep 5 && \
        apt-get install -y --no-install-recommends \
            poppler-utils \
            tesseract-ocr \
            antiword \
            unrtf \
    || echo "Warning: Document tools installation failed, continuing...")) && \
    # Install audio processing tools (optional - continue even if they fail)
    (apt-get install -y --no-install-recommends \
        flac \
        ffmpeg \
        lame \
        libmad0 \
        libsox-fmt-mp3 \
        sox \
        swig \
        libpulse-dev \
    || echo "Warning: Audio packages failed to install, continuing without them...") && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/media /app/logs /app/volumes

# Copy application code
COPY . .

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/admin/ || exit 1

# Default command - runs migrations, sets up container data, and starts server
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate && python manage.py setup_container_data && python manage.py runserver 0.0.0.0:8000"]
