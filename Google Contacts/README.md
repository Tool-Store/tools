Google Contacts MCP Tool

Overview
- Provides Model Context Protocol (MCP) tools to search, read, update, delete, and export Google Contacts, including handling contact photos and today’s birthdays.
- Integrates with the Tool Store Developer API for per-user data (OAuth token retrieval) and file storage (CSV exports).

Key Features
- OAuth via Tool Store activation (Google provider with People API scopes).
- DRY, fail-fast Python implementation using an MCP server (`mcp` Python library).
- No dummy data; all actions operate on the user’s Google account through the Google People API.
- Import/export: Supports CSV and VCF exports to Tool Store storage, and VCF import from a public URL or from Tool Store storage.

Files
- `tool-data.yaml`: Tool Store configuration, actions, activation steps, and function specs.
- `Dockerfile`: Container that runs the MCP server over stdio.
- `.env.example`: Variables required by the tool at runtime.
- `.env`: Local override of env vars (do not commit secrets).
- `server.py`: MCP server definition and tool implementations.
- `google_contacts.py`: Google People API client wrappers.
- `toolstore_client.py`: Tool Store Developer API client for user data and storage.
- `prompts/usage.md`: Guidance for AIs on how to use the tool and actions.
  
Additional Dependencies
- `vobject` is used to read/write VCF files for import/export operations.

Runtime Expectations
- The Tool Store host injects a Firebase JWT for the current user and identifiers for the developer, tool, and user so the server can retrieve OAuth credentials from Tool User Data.
- Access tokens are expected to be available in Tool User Data after activation. If missing or expired, the tool returns a clear error instructing the user to re-connect via activation.

Notes
- Automatic token refresh: If `TOOLSTORE_OAUTH_TOKEN_ENDPOINT` is configured and user data includes a `refresh_token`, the server will attempt to refresh and persist a new `access_token` seamlessly. Otherwise, users must re-run activation when tokens expire.
