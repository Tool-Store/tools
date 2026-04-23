# ARCHITECTURE_INDEX.md (Tool Architecture Map)

## Canonical tool tree

```text
.
├─ server.py                    # MCP server entrypoint, tool registration, request handling
├─ google_contacts.py           # Google People API client, domain logic, data transforms
├─ toolstore_client.py          # Tool Store Developer API client (auth, user data, storage, OAuth refresh)
├─ tool-data.yaml               # MCP contract: metadata, functions, resources, activation, pricing
├─ .env / .env.example          # Environment configuration for local development
├─ Dockerfile                   # Container runtime definition
├─ README.md                    # Tool-specific usage documentation
└─ prompts/                     # LLM prompts for tool behavior
   └─ system.md                 # System prompt for contact management context
```

## Service ownership map

- **MCP server lifecycle**: `server.py` - initializes FastMCP, registers tools/resources, handles requests
- **Google API integration**: `google_contacts.py` - all Google People API calls, contact transformations
- **Platform integration**: `toolstore_client.py` - Tool Store auth, user data CRUD, storage operations, token refresh
- **Contract definition**: `tool-data.yaml` - single source of truth for MCP interface and marketplace metadata
- **Runtime environment**: `Dockerfile` + `.env` - container and configuration

## Ownership boundaries

- `server.py` owns request routing and MCP protocol handling
- `google_contacts.py` owns all external Google API interactions
- `toolstore_client.py` owns all Tool Store platform interactions
- Each module validates inputs at its boundary before calling external services
- No module reaches directly into another's implementation details

## Where changes belong

- Add new MCP tools/resources → `server.py` (registration) + `google_contacts.py` (implementation)
- Change Google API interactions → `google_contacts.py` only
- Change platform integration → `toolstore_client.py` only
- Change activation/pricing/metadata → `tool-data.yaml` only
- Change environment requirements → `.env.example` + `Dockerfile` if needed

## Dependencies

- External: Google People API v1, Tool Store Developer API
- Internal: `toolstore_client.py` used by `google_contacts.py` for token refresh and storage
- Runtime: MCP SDK, `requests`, `python-dotenv`

## Update rule

If file/module locations change, update this file in the same patch.
