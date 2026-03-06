# ── Build stage ──────────────────────────────────────────────────────────────
# Install Python dependencies in an isolated layer so the final image
# only contains what is needed at runtime.
FROM python:3.12-slim AS builder

WORKDIR /build

# curl_cffi wheels include libcurl compiled with BoringSSL; they are
# pre-built for manylinux so no system build tools are required.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

# curl is only needed for the HEALTHCHECK; install it and clean up in one layer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from the builder stage.
COPY --from=builder /install /usr/local

WORKDIR /app

# Run as a non-root user for better container security.
RUN adduser --disabled-password --gecos "" appuser \
    && chown appuser /app
USER appuser

# Copy application source.
COPY --chown=appuser:appuser app/ ./app/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
