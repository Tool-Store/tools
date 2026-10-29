# PROJECT.md (Tool Definition)

Social Media Scraper is an MCP tool that lets AI agents read public content from the web and social platforms. Pages are fetched through Jina Reader and returned as clean markdown; YouTube transcripts are read from subtitles or auto-captions via yt-dlp without downloading video. Public Instagram, Facebook page, LinkedIn and X profiles and posts are read through Apify scrapers that need no login; public Telegram channels are read from their `t.me/s` web preview.

This tool runs as an MCP server on the Tool Store platform. Each user can optionally add their own API keys through activation; no key is required for the core tools.

## It should

- Read any public web page and return it as markdown.
- Return the transcript of a public YouTube video in a requested language.
- Return public profiles and recent posts from Instagram, Facebook pages, LinkedIn and X.
- Return recent posts of a public Telegram channel.
- Work immediately after install with no user credentials.
- Use a user's optional Jina API key for higher rate limits when provided.
- Limit every response size so results fit in an AI context window.

## Capabilities

### MCP Functions

- `scrape_url` - Read a public web page via Jina Reader and return markdown (truncated to `max_chars`).
- `get_youtube_transcript` - Return a YouTube video's transcript from subtitles or auto-captions (truncated to `max_chars`).
- `get_telegram_channel_posts` - Return recent posts of a public Telegram channel from its `t.me/s` preview via Jina Reader (truncated to `max_chars`).
- `get_social_profile` - Return a public Instagram, Facebook page, LinkedIn or X profile via Apify (truncated to `max_chars`).
- `get_social_posts` - Return up to 50 recent public posts of an Instagram, Facebook page, LinkedIn or X profile via Apify (truncated to `max_chars`).

## Technical stack

- Python 3.11 runtime
- MCP Python SDK (FastMCP-style server registration)
- Jina Reader API (`r.jina.ai`)
- `yt-dlp` with Deno as its JavaScript runtime
- Apify actors via the `run-sync-get-dataset-items` API (Instagram, Facebook, LinkedIn, X)
- HTTP via `requests`
- Tool Store Developer API for activation secrets (`toolstore_client.py`)

## Activation requirements

- Optional form step with `JINA_API_KEY` (password, secret). Stored per user by Tool Store and read by `server.py` through `toolstore_client.py` on each call.
- `APIFY_API_TOKEN` is a Tool Store-level server environment variable, not a user activation field: Tool Store pays for Apify usage.

## Configuration

- `tool-data.yaml` - MCP contract, metadata, activation steps, pricing
- `.env` / `.env.example` - Environment variables for local development
- `Dockerfile` - Container runtime definition

## Quality constraints

- Validate URLs (absolute http/https; YouTube hosts only for transcripts) and `max_chars` before any network call
- Every outbound request has a timeout
- Upstream failures raise explicit errors with platform and status; no silent fallbacks
- Never log API keys
- Every Apify run is capped by `maxTotalChargeUsd` and `limit` is capped at 50 posts, so one call cannot drain the Apify credit
- Only public data, read without logging in to any social account

## Open questions

- Whether YouTube blocks yt-dlp from the cloud runtime (Phase 0)
- Apify Free plan limits per actor: the X actors allow 5 runs/month of 10 items each; `harvestapi/linkedin-profile-scraper` allows 50 runs total
- Per-user usage limits and pricing before production (Tool Store pays for Apify)
