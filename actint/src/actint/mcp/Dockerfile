# Dockerfile for AIS Vessel Intelligence MCP System

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire actint package
# This assumes docker is built from the parent directory
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Build argument for service type
ARG SERVICE=mcp
ENV SERVICE=${SERVICE}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${SERVICE_PORT:-8001}/health || exit 1

# Default command (will be overridden by docker-compose.yml)
CMD ["python", "-m", "actint.mcp.mcp_server"]
