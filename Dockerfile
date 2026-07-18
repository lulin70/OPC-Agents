ARG VERSION=0.3.35

# Stage 1: Builder — install build dependencies and compile
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency files and install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime — copy only installed packages, no build tools
FROM python:3.11-slim

LABEL maintainer="OPC-Agents Team"
LABEL version="${VERSION}"
LABEL description="AI-Powered Personal Business Assistant"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 opcuser && chown -R opcuser:opcuser /app
USER opcuser

# Create data directory
RUN mkdir -p /app/data

# Expose Streamlit port
EXPOSE 8501

# Health check — verify both HTTP and database connectivity
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health && python -c "from opc_manager.data_manager import execute_query; execute_query('SELECT 1')" || exit 1

# Environment defaults
ENV OPC_LOCALE=zh_CN \
    OPC_DATA_DIR=/app/data \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true

CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.headless=true"]
