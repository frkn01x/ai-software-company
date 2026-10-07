# ─── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları önce kopyala (layer cache için)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Güvenlik: root olmayan kullanıcı (home dizini ile)
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

WORKDIR /app

# Builder'dan kurulu paketleri kopyala
COPY --from=builder /install /usr/local

# Uygulama kodunu kopyala
COPY --chown=appuser:appuser . .

# Gerekli dizinleri oluştur
RUN mkdir -p logs state vault output && \
    chown -R appuser:appuser logs state vault output /home/appuser

# Non-root kullanıcıya geç
USER appuser

# Ortam değişkenleri
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HOME=/home/appuser \
    CREWAI_STORAGE_DIR=/app/state

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Giriş noktası
CMD ["python", "main.py"]
