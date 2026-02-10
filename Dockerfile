# ===================================
# Multi-stage Dockerfile for DrishtriKon CTF Platform
# Optimized for production deployment
# ===================================

FROM python:3.11-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ===================================
# Production stage
# ===================================
FROM python:3.11-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    FLASK_APP=wsgi:app \
    FLASK_ENV=production

# Create app user for security
RUN groupadd -r ctf && useradd -r -g ctf ctf

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=ctf:ctf . /app

# Create runtime directories
RUN mkdir -p /app/var/logs /app/var/cache /app/var/uploads \
    /app/honeypot_data /app/ids_data && \
    chown -R ctf:ctf /app/var /app/honeypot_data /app/ids_data

# Switch to non-root user
USER ctf

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/healthz')" || exit 1

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "wsgi:app"]
