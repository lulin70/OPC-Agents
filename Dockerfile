FROM python:3.11-slim

LABEL maintainer="OPC-Agents Team"
LABEL version="0.2.2"
LABEL description="AI-Powered Personal Business Assistant"

WORKDIR /app

# Install system dependencies for PDF/Word export
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency files first (for Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 opcuser && chown -R opcuser:opcuser /app
USER opcuser

# Create data directory
RUN mkdir -p /app/data

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Environment defaults
ENV OPC_LOCALE=zh_CN \
    OPC_DATA_DIR=/app/data \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true

CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.headless=true"]
