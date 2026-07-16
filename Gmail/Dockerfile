# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Copy files
COPY server.py toolstore_client.py gmail.py ./
COPY .env .env

# Install deps
RUN pip install --no-cache-dir \
    mcp \
    python-dotenv \
    requests

# Default command runs the MCP server over stdio
CMD ["python", "server.py"]
