FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies if needed (e.g. for psycopg or cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies in a virtual env
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
# Create a dummy app structure to install dependencies
RUN mkdir -p app && touch app/__init__.py
RUN pip install --no-cache-dir .

# Now copy the actual application code
COPY app/ ./app/
COPY alembic.ini ./
COPY migrations/ ./migrations/

# Stage 2: Runner
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (libpq is needed for psycopg if not using binary, but we use binary)
# Still good to have just in case.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application files
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/migrations /app/migrations

RUN mkdir -p /app/storage/recordings /app/storage/evidence /app/storage/kyc && chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Healthcheck for orchestrator / Docker Compose
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/live || exit 1

# Start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
