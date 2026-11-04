# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS node

FROM python:3.11-slim-bookworm

# Pinned commit of the Tool-Store fork; bump deliberately after syncing the fork.
ARG AGENT_REACH_REF=b7425906aab8c2b5a7dc17fc07c2b9973bdce732

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    REACH_BROWSER_LOCALE=en-US \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

# chromium supplies the shared libraries CloakBrowser needs and a system Chrome fallback.
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates \
    chromium \
    fonts-liberation \
    novnc \
    websockify \
    x11vnc \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN python -m venv /opt/agent-reach \
    && /opt/agent-reach/bin/pip install --no-cache-dir \
    "https://github.com/Tool-Store/Agent-Reach/archive/${AGENT_REACH_REF}.zip" \
    && ln -s /opt/agent-reach/bin/agent-reach /usr/local/bin/agent-reach

# ~/.agent-reach holds logins and the browser profile; it is mounted as a volume.
RUN useradd --create-home --uid 1000 agent \
    && install -d -m 700 -o agent -g agent /home/agent/.agent-reach \
    && install -d -m 1777 /tmp/.X11-unix

COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Playwright's Chromium for the per-request browser sessions, in a path the agent user can read.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*
COPY server.py constants.py errors.py validators.py caller.py sessions.py login_store.py file_store.py \
    browser_session.py responses.py agent_reach.py command_runner.py ./
COPY linkedin ./linkedin
COPY page_scripts ./page_scripts
# Licenses and NOTICE of the Apache-2.0 code ported into linkedin/ and page_scripts/
COPY third_party ./third_party

USER agent

EXPOSE 6080 8000

ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "server.py"]
