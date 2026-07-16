Gmail MCP Tool

Overview
- Provides Model Context Protocol (MCP) tools to list, search, read, send, reply, forward, and organize Gmail messages, manage drafts and labels, and download attachments.
- Integrates with the Tool Store Developer API for per-user OAuth token retrieval and file storage.

Key Features
- OAuth via Tool Store activation (Google provider with `gmail.modify` scope).
- Fail-fast Python implementation using an MCP server (`mcp` Python library).
- All operations act on the authenticated user's Gmail account via Gmail API v1.
- Attachments: download to Tool Store storage; attach files from Tool Store storage when sending.
- Threading preserved on replies (`In-Reply-To`, `References`, `threadId`).

Files
- `tool-data.yaml`: Tool Store configuration, actions, activation steps, and function specs.
- `Dockerfile`: Container that runs the MCP server over stdio.
- `.env.example`: Variables required by the tool at runtime.
- `.env`: Local override of env vars (do not commit secrets).
- `server.py`: MCP server definition and tool implementations.
- `gmail.py`: Gmail API v1 client and MIME utilities.
- `toolstore_client.py`: Tool Store Developer API client for user data and storage.
- `prompts/usage.md`: Guidance for AIs on how to use the tool and actions.

Runtime Expectations
- The Tool Store host injects a Firebase JWT for the current user and identifiers for the developer, tool, and user so the server can retrieve OAuth credentials from Tool User Data.
- Access tokens are expected to be available in Tool User Data after activation. If missing or expired, the tool returns a clear error instructing the user to re-connect via activation.

Notes
- Automatic token refresh: If `TOOLSTORE_OAUTH_TOKEN_ENDPOINT` is configured and user data includes a `refresh_token`, the server will refresh and persist a new `access_token` seamlessly. Otherwise, users must re-run activation when tokens expire.
- `gmail.modify` permits read, send, label, and trash/untrash. It does NOT allow permanent deletion of messages other than via the explicit `users.messages.delete` endpoint, which still requires `modify` scope per Gmail API documentation.
