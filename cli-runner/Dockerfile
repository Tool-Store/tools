# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CLI_RUNNER_STATE_PATH=/app/data/installed.json

WORKDIR /app

RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/data

COPY server.py cli_runtime.py ./

RUN pip install --no-cache-dir \
    mcp \
    python-dotenv

CMD ["python", "server.py"]
