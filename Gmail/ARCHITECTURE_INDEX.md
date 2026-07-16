# ARCHITECTURE_INDEX.md (Tool Architecture Map)

## Canonical tool tree

```text
.
├─ server.py                    # MCP server entrypoint, tool registration, request handling
├─ gmail.py                     # Gmail API v1 client, MIME construction, response parsing
├─ toolstore_client.py          # Tool Store Developer API client (auth, user data, storage, OAuth refresh)
├─ tool-data.yaml               # MCP contract: metadata, functions, activation, pricing
├─ .env / .env.example          # Environment configuration for local development
├─ Dockerfile                   # Container runtime definition
├─ README.md                    # Tool-specific usage documentation
└─ prompts/                     # LLM prompts for tool behavior
   └─ usage.md                  # AI usage guidance for Gmail operations
```

## Service ownership map

- **MCP server lifecycle**: `server.py` - initializes the MCP server, registers tools, handles requests
- **Gmail API integration**: `gmail.py` - all Gmail API v1 calls, MIME assembly, payload parsing
- **Platform integration**: `toolstore_client.py` - Tool Store auth, user data, storage, OAuth refresh
- **Contract definition**: `tool-data.yaml` - single source of truth for MCP interface and marketplace metadata
- **Runtime environment**: `Dockerfile` + `.env` - container and configuration

## Ownership boundaries

- `server.py` owns request routing, MCP protocol handling, and attachment resolution from Tool Store storage
- `gmail.py` owns all external Gmail API interactions and email content shaping
- `toolstore_client.py` owns all Tool Store platform interactions
- Each module validates inputs at its boundary before calling external services
- No module reaches directly into another's implementation details

## Where changes belong

- Add new MCP tools/resources → `server.py` (registration) + `gmail.py` (implementation)
- Change Gmail API interactions → `gmail.py` only
- Change platform integration → `toolstore_client.py` only
- Change activation/pricing/metadata → `tool-data.yaml` only
- Change environment requirements → `.env.example` + `Dockerfile` if needed

## Dependencies

- External: Gmail API v1, Tool Store Developer API
- Internal: `toolstore_client.py` used by `server.py` for token refresh, storage upload/download
- Runtime: MCP SDK, `requests`, `python-dotenv`, Python stdlib (`email`, `base64`)

## Update rule

If file/module locations change, update this file in the same patch.
