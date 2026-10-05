# ARCHITECTURE_INDEX.md (Tool Architecture Map)

## Canonical tool tree

```text
.
├─ server.py                    # MCP server entrypoint, tool registration
├─ scraper.py                   # Jina Reader and yt-dlp integrations, input validation, response shaping
├─ toolstore_client.py          # Tool Store Developer API client (auth, user data, activation secrets)
├─ tool-data.yaml               # MCP contract: metadata, functions, activation, pricing
├─ .env / .env.example          # Environment configuration for local development
├─ Dockerfile                   # Container runtime definition (Python + Deno for yt-dlp)
└─ README.md                    # Tool-specific usage documentation
```

## Service ownership map

- **MCP server lifecycle**: `server.py` - initializes the MCP server, registers tools, resolves activation secrets
- **External integrations**: `scraper.py` - all Jina Reader, YouTube and subtitle HTTP calls
- **Platform integration**: `toolstore_client.py` - Tool Store auth, user data, activation secrets
- **Contract definition**: `tool-data.yaml` - single source of truth for MCP interface and marketplace metadata
- **Runtime environment**: `Dockerfile` + `.env` - container and configuration

## Ownership boundaries

- `server.py` owns MCP protocol handling, reads the optional `JINA_API_KEY` via `toolstore_client.py`, and delegates every call to `scraper.py`
- `scraper.py` owns all outbound network calls, input validation, and result truncation; it receives credentials as arguments
- `toolstore_client.py` owns all Tool Store platform interactions

## Where changes belong

- Add new MCP tools → `server.py` (registration) + `scraper.py` (implementation)
- Change platform integrations → `scraper.py` only
- Change Tool Store integration → `toolstore_client.py` only
- Change activation/pricing/metadata → `tool-data.yaml` only
- Change environment requirements → `.env.example` + `Dockerfile` if needed

## Dependencies

- External: Jina Reader API, YouTube (via yt-dlp), Tool Store Developer API
- Internal: `toolstore_client.py` used by `server.py` for activation secrets
- Runtime: MCP SDK, `requests`, `python-dotenv`, `yt-dlp`, Deno

## Update rule

If file/module locations change, update this file in the same patch.
