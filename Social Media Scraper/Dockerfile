# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp needs a JavaScript runtime to solve YouTube player challenges
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

COPY server.py scraper.py toolstore_client.py ./

RUN pip install --no-cache-dir \
    "mcp<2" \
    python-dotenv \
    requests \
    "yt-dlp[default]"

CMD ["python", "server.py"]
