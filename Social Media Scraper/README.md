Social Media Scraper MCP Tool

Overview
- Provides Model Context Protocol (MCP) tools to read public web pages, YouTube transcripts, Telegram channels and Instagram, Facebook, LinkedIn and X profiles and posts.
- Works with no user credentials; an optional Jina API key raises web-reading rate limits.

Key Features
- `scrape_url`: any public web page returned as markdown via Jina Reader.
- `get_youtube_transcript`: transcript from subtitles or auto-captions via yt-dlp (no video download).
- `get_telegram_channel_posts`: recent posts of a public Telegram channel from its `t.me/s` preview.
- `get_social_profile` / `get_social_posts`: public profiles and up to 50 recent posts from `instagram`, `facebook` (public pages), `linkedin` or `x`, via Apify scrapers that need no login.
- Every response is truncated to `max_chars` (default 20000, max 100000) and reports whether it was truncated.
- Every Apify run is capped at $0.50 (`maxTotalChargeUsd`).

Files
- `tool-data.yaml`: Tool Store configuration, function specs, and optional activation form.
- `Dockerfile`: Container with Python, yt-dlp and Deno (yt-dlp's JavaScript runtime for YouTube).
- `.env.example`: Variables used by the tool at runtime.
- `.env`: Local override of env vars (do not commit secrets).
- `server.py`: MCP server definition and tool registration.
- `scraper.py`: Jina Reader, Telegram preview and YouTube integrations.
- `social_platforms.py`: Apify integration for Instagram, Facebook, LinkedIn and X.
- `toolstore_client.py`: Tool Store Developer API client for user data and activation secrets.

Runtime Expectations
- In Tool Store, `server.py` reads the user's optional `JINA_API_KEY` from activation secrets via `toolstore_client.py`. If the user has not added one, requests use Jina's keyless rate limit.
- Without a Tool Store JWT (local development), `JINA_API_KEY` is read from `.env`.
- `APIFY_API_TOKEN` is read from the server environment. It is a Tool Store-level key, not a user activation field. Without it, the social platform tools return a clear "not configured" error.

Local Development
- Copy `.env.example` to `.env`, optionally set `JINA_API_KEY`, and set `APIFY_API_TOKEN` (free Apify account, no card) to use the social platform tools.
- Install dependencies: `pip install mcp python-dotenv requests "yt-dlp[default]"` and install Deno for YouTube support.
- Run: `python server.py` (stdio transport by default; set `MCP_TRANSPORT` to change it).
