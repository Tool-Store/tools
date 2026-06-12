# PROJECT.md (Tool Definition)

Gmail is an MCP tool that provides email management capabilities through the Gmail API v1. It allows users to list, search, read, send, reply, forward, organize, and manage drafts and labels in their Gmail account, plus download attachments into Tool Store storage.

This tool runs as an MCP server and integrates with the Tool Store platform for authentication, user data storage, and file management.

## It should

- Allow users to list, search, and read messages and threads using Gmail query syntax.
- Send new messages, reply with proper threading, and forward existing messages.
- Manage drafts: create, update, list, send, and delete.
- Manage labels: list, create, delete, and apply/remove labels on messages.
- Move messages to trash, restore them, or permanently delete.
- Download attachments and upload them to Tool Store storage.
- Attach files from Tool Store storage when sending messages.
- Use OAuth-based activation to connect a user's Google account securely.

## Capabilities

### MCP Functions

Messaging
- `list_messages` - List or search messages by Gmail query (`q`), labels, and pagination.
- `get_message` - Retrieve a message with parsed headers, plain/HTML body, and attachment metadata.
- `get_thread` - Retrieve a full conversation thread.
- `send_message` - Send a new email with optional CC/BCC, HTML body, and storage-based attachments.
- `reply_to_message` - Reply to a message preserving threading (`In-Reply-To`, `References`, `threadId`).
- `forward_message` - Forward a message with an optional additional note.
- `trash_message` - Move a message to Trash.
- `untrash_message` - Restore a message from Trash.
- `delete_message` - Permanently delete a message.
- `modify_message_labels` - Add and/or remove label ids on a message (covers mark read/unread, star, archive).

Drafts
- `list_drafts` - List drafts with optional query and pagination.
- `get_draft` - Retrieve a draft by id.
- `create_draft` - Create a new draft (supports threading and attachments).
- `update_draft` - Replace the content of an existing draft.
- `send_draft` - Send an existing draft.
- `delete_draft` - Delete a draft.

Labels
- `list_labels` - List all labels (system and user).
- `create_label` - Create a user label with visibility settings.
- `delete_label` - Delete a user label.

Attachments
- `download_attachment` - Download an attachment by id, save it to Tool Store storage, and return its storage path.

Profile
- `get_profile` - Get the authenticated user's email address and message/thread totals.

## Technical stack

- Python 3.x runtime
- MCP Python SDK (FastMCP-style server registration)
- Gmail API v1 (REST)
- Tool Store Developer API for user data, OAuth refresh, and storage
- HTTP/REST clients via `requests` library
- Standard library `email.message.EmailMessage` for RFC 5322 MIME construction

## Activation requirements

- OAuth 2.0 flow for Google account authorization
- Required scope: `https://www.googleapis.com/auth/gmail.modify`
- Per-user OAuth tokens stored in Tool Store user data (managed by `toolstore_client`)

## Configuration

- `tool-data.yaml` - MCP contract, metadata, activation steps, pricing
- `.env` / `.env.example` - Environment variables for local development
- `Dockerfile` - Container runtime definition

## Quality constraints

- Validate all user inputs before Gmail API calls (fail fast on missing required fields)
- Handle OAuth token refresh automatically via Tool Store platform
- Use base64url (unpadded) encoding for raw RFC 5322 messages as required by Gmail API
- Preserve threading headers on replies and forwards
- Log errors explicitly with HTTP status and Gmail API error payload
- Keep user data and storage operations within Tool Store platform boundaries
- Never log message bodies or recipient lists at INFO level

## Open questions

- Push notifications via Gmail watch endpoint (not in v1)
- Bulk operations performance limits (Gmail API quota is per-user/per-second)
- Rich attachment preview/transformation
