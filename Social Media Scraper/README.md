Social Media Scraper MCP Tool

Overview
- Provides Model Context Protocol (MCP) tools to read public web pages and YouTube transcripts.
- Works immediately with no credentials; an optional Jina API key raises web-reading rate limits.

Key Features
- `scrape_url`: any public web page returned as markdown via Jina Reader.
- `get_youtube_transcript`: transcript from subtitles or auto-captions via yt-dlp (no video download).
- Every response is truncated to `max_chars` (default 20000, max 100000) and reports whether it was truncated.

Files
- `tool-data.yaml`: Tool Store configuration, function specs, and optional activation form.
- `Dockerfile`: Container with Python, yt-dlp and Deno (yt-dlp's JavaScript runtime for YouTube).
- `.env.example`: Variables used by the tool at runtime.
- `.env`: Local override of env vars (do not commit secrets).
- `server.py`: MCP server definition and tool registration.
- `scraper.py`: Jina Reader and YouTube integrations.
- `toolstore_client.py`: Tool Store Developer API client for user data and activation secrets.

Runtime Expectations
- In Tool Store, `server.py` reads the user's optional `JINA_API_KEY` from activation secrets via `toolstore_client.py`. If the user has not added one, requests use Jina's keyless rate limit.
- Without a Tool Store JWT (local development), `JINA_API_KEY` is read from `.env`.

Local Development
- Copy `.env.example` to `.env` and optionally set `JINA_API_KEY`.
- Install dependencies: `pip install mcp python-dotenv requests "yt-dlp[default]"` and install Deno for YouTube support.
- Run: `python server.py` (stdio transport by default; set `MCP_TRANSPORT` to change it).
