# ARCHITECTURE_INDEX.md (Tool Architecture Map)

## Canonical tool tree

```text
.
├─ server.py                    # MCP server entrypoint, tool registration
├─ scraper.py                   # Jina Reader, Telegram preview and yt-dlp integrations, input validation, response shaping
├─ social_platforms.py          # Apify integration for Instagram, Facebook, LinkedIn and X profiles and posts
├─ toolstore_client.py          # Tool Store Developer API client (auth, user data, activation secrets)
├─ tool-data.yaml               # MCP contract: metadata, functions, activation, pricing
├─ .env / .env.example          # Environment configuration for local development
├─ Dockerfile                   # Container runtime definition (Python + Deno for yt-dlp)
└─ README.md                    # Tool-specific usage documentation
```

## Service ownership map

- **MCP server lifecycle**: `server.py` - initializes the MCP server, registers tools, resolves activation secrets
- **External integrations**: `scraper.py` - all Jina Reader, Telegram preview, YouTube and subtitle HTTP calls
- **Social platform integrations**: `social_platforms.py` - all Apify actor calls (actor IDs, inputs, spending cap)
- **Platform integration**: `toolstore_client.py` - Tool Store auth, user data, activation secrets
- **Contract definition**: `tool-data.yaml` - single source of truth for MCP interface and marketplace metadata
- **Runtime environment**: `Dockerfile` + `.env` - container and configuration

## Ownership boundaries

- `server.py` owns MCP protocol handling, reads the optional `JINA_API_KEY` via `toolstore_client.py` and `APIFY_API_TOKEN` from the environment, and delegates every call to `scraper.py` or `social_platforms.py`
- `scraper.py` owns Jina, Telegram and YouTube calls, input validation, and result truncation; it receives credentials as arguments
- `social_platforms.py` owns Apify calls and reuses `scraper.py` validation and truncation; it receives the Apify token as an argument
- `toolstore_client.py` owns all Tool Store platform interactions

## Where changes belong

- Add new MCP tools → `server.py` (registration) + `scraper.py` or `social_platforms.py` (implementation)
- Change web, Telegram or YouTube integrations → `scraper.py` only
- Change Instagram, Facebook, LinkedIn or X integrations (actor IDs, inputs) → `social_platforms.py` only
- Change Tool Store integration → `toolstore_client.py` only
- Change activation/pricing/metadata → `tool-data.yaml` only
- Change environment requirements → `.env.example` + `Dockerfile` if needed

## Dependencies

- External: Jina Reader API, YouTube (via yt-dlp), Apify API, Tool Store Developer API
- Internal: `toolstore_client.py` used by `server.py` for activation secrets
- Runtime: MCP SDK, `requests`, `python-dotenv`, `yt-dlp`, Deno

## Update rule

If file/module locations change, update this file in the same patch.
