FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies if needed (e.g. for psycopg or cryptography)
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies in a virtual env
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
# Create a dummy app structure to install dependencies
RUN mkdir -p app && touch app/__init__.py
# Upgrade build tools, install production dependencies, and remove build tools from venv
# to eliminate any vulnerabilities in pip/setuptools/wheel/jaraco from the production image
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir . && \
    pip uninstall -y pip setuptools wheel

# Now copy the actual application code
COPY app/ ./app/
COPY alembic.ini ./
COPY migrations/ ./migrations/

# Stage 2: Runner
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install runtime dependencies and upgrade base packages to remediate known CVEs
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
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
