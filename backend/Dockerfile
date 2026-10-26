# ==============================================================================
# DataQuery Backend Dockerfile — Non-Root Python 3.12 Production Image
# ==============================================================================

FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install curl for health checks and clean apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create secure non-root system user and group
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/sh -m appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application source code
COPY . .

# Set executable permissions on entrypoint and ownership to non-root user
RUN chmod +x entrypoint.sh && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8000

# Health check using the /api/v1/health endpoint
HEALTHCHECK --interval=5s --timeout=5s --retries=5 --start-period=10s \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

ENTRYPOINT ["/bin/sh", "entrypoint.sh"]
