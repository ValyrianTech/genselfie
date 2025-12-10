# GenSelfie RunPod Serverless Worker
# 
# This Dockerfile creates a serverless worker that can be deployed on RunPod.
# It expects to run alongside a ComfyUI instance (either on the same pod or accessible via network).
#
# For a complete solution, use this with the ValyrianTech ComfyUI template.

# Build stage
FROM python:3.11-slim AS builder

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
FROM python:3.11-slim

WORKDIR /

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy handler
COPY handler.py /handler.py

# Create workflows directory (workflow should be mounted or copied separately)
RUN mkdir -p /workflows

# Environment variables
ENV COMFYUI_URL=http://127.0.0.1:8188
ENV WORKFLOW_PATH=/workflows/genselfie.json

# Run the handler
CMD ["python", "-u", "/handler.py"]
