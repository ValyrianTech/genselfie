# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.12-slim AS production

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY main.py config.py database.py ./
COPY routers/ ./routers/
COPY services/ ./services/
COPY templates/ ./templates/
COPY static/ ./static/
COPY workflows/ ./workflows/

# Create default data directory (default: /workspace for RunPod compatibility)
RUN mkdir -p /workspace/uploads

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000"]
