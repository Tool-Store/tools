import logging
import mimetypes
import os
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from toolstore_client import ToolStoreClient
from gmail import GmailClient

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO))


def _gmail_client(ts: ToolStoreClient) -> GmailClient:
    """Instantiate a Gmail API client with a valid access token from Tool Store data."""
    token = ts.get_oauth_access_token("google")
    return GmailClient(token)


def _resolve_storage_attachments(
    ts: ToolStoreClient,
    storage_paths: Optional[List[str]],
) -> Optional[List[Dict[str, Any]]]:
    """Fetch each Tool Store storage file and return a list of attachment dicts for GmailClient."""
    if not storage_paths:
        return None

    attachments: List[Dict[str, Any]] = []
    for path in storage_paths:
        download_url = ts.get_download_url(path)
        if not download_url:
            raise RuntimeError(f"Could not resolve download URL for attachment: {path}")
        resp = requests.get(download_url, timeout=60)
        if not resp.ok:
            raise RuntimeError(f"Failed to download attachment '{path}': {resp.status_code}")
        file_name = path.rsplit("/", 1)[-1] or "attachment"
        content_type = (
            resp.headers.get("Content-Type")
            or mimetypes.guess_type(file_name)[0]
            or "application/octet-stream"
        )
        attachments.append({
            "file_name": file_name,
            "content_bytes": resp.content,
            "content_type": content_type,
        })
    return attachments


def _text(payload: Any) -> List[TextContent]:
    """Wrap a Python value as a single TextContent block for MCP responses."""
    return [TextContent(type="text", text=str(payload))]


def create_server() -> FastMCP:
    """Create the MCP server and register Gmail tools."""
    load_dotenv()
    _setup_logging()
    server = FastMCP("gmail")

    ts = ToolStoreClient()

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    @server.tool()
    def get_profile() -> List[TextContent]:
        """Get the authenticated user's email address and message/thread totals."""
        return _text(_gmail_client(ts).get_profile())

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------
    @server.tool()
    def list_messages(
        q: Optional[str] = None,
        label_ids: Optional[List[str]] = None,
        max_results: int = 50,
        page_token: Optional[str] = None,
    ) -> List[TextContent]:
        """List or search messages using Gmail query syntax."""
        return _text(
            _gmail_client(ts).list_messages(
                q=q, label_ids=label_ids, max_results=max_results, page_token=page_token
            )
        )

    @server.tool()
    def get_message(message_id: str) -> List[TextContent]:
        """Get a message with parsed headers, plain/HTML body, and attachment metadata."""
        return _text(_gmail_client(ts).get_message(message_id))

    @server.tool()
    def get_thread(thread_id: str) -> List[TextContent]:
        """Get a full conversation thread by id."""
        return _text(_gmail_client(ts).get_thread(thread_id))

    @server.tool()
    def send_message(
        to: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        subject: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachment_storage_paths: Optional[List[str]] = None,
    ) -> List[TextContent]:
        """Send a new email. Attachments come from Tool Store storage paths."""
        client = _gmail_client(ts)
        attachments = _resolve_storage_attachments(ts, attachment_storage_paths)
        return _text(client.send_message(
            to=to, cc=cc, bcc=bcc, subject=subject,
            body_text=body_text, body_html=body_html,
            attachments=attachments,
        ))

    @server.tool()
    def reply_to_message(
        message_id: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachment_storage_paths: Optional[List[str]] = None,
    ) -> List[TextContent]:
        """Reply to a message preserving threading."""
        client = _gmail_client(ts)
        attachments = _resolve_storage_attachments(ts, attachment_storage_paths)
        return _text(client.reply_to_message(
            message_id=message_id,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        ))

    @server.tool()
    def forward_message(
        message_id: str,
        to: str,
        additional_text: Optional[str] = None,
        additional_html: Optional[str] = None,
    ) -> List[TextContent]:
        """Forward an existing message to new recipients."""
        return _text(_gmail_client(ts).forward_message(
            message_id=message_id,
            to=to,
            additional_text=additional_text,
            additional_html=additional_html,
        ))

    @server.tool()
    def trash_message(message_id: str) -> List[TextContent]:
        """Move a message to Trash."""
        return _text(_gmail_client(ts).trash_message(message_id))

    @server.tool()
    def untrash_message(message_id: str) -> List[TextContent]:
        """Restore a message from Trash."""
        return _text(_gmail_client(ts).untrash_message(message_id))

    @server.tool()
    def delete_message(message_id: str) -> List[TextContent]:
        """Permanently delete a message."""
        _gmail_client(ts).delete_message(message_id)
        return _text({"deleted": message_id})

    @server.tool()
    def modify_message_labels(
        message_id: str,
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None,
    ) -> List[TextContent]:
        """Add and/or remove labels on a message."""
        return _text(_gmail_client(ts).modify_message_labels(
            message_id=message_id,
            add_label_ids=add_label_ids,
            remove_label_ids=remove_label_ids,
        ))

    # ------------------------------------------------------------------
    # Drafts
    # ------------------------------------------------------------------
    @server.tool()
    def list_drafts(
        q: Optional[str] = None,
        max_results: int = 50,
        page_token: Optional[str] = None,
    ) -> List[TextContent]:
        """List drafts with optional query and pagination."""
        return _text(_gmail_client(ts).list_drafts(q=q, max_results=max_results, page_token=page_token))

    @server.tool()
    def get_draft(draft_id: str) -> List[TextContent]:
        """Get a draft by id."""
        return _text(_gmail_client(ts).get_draft(draft_id))

    @server.tool()
    def create_draft(
        to: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        subject: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachment_storage_paths: Optional[List[str]] = None,
    ) -> List[TextContent]:
        """Create a new draft."""
        client = _gmail_client(ts)
        attachments = _resolve_storage_attachments(ts, attachment_storage_paths)
        return _text(client.create_draft(
            to=to, cc=cc, bcc=bcc, subject=subject,
            body_text=body_text, body_html=body_html,
            attachments=attachments,
        ))

    @server.tool()
    def update_draft(
        draft_id: str,
        to: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        subject: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachment_storage_paths: Optional[List[str]] = None,
    ) -> List[TextContent]:
        """Replace the content of a draft."""
        client = _gmail_client(ts)
        attachments = _resolve_storage_attachments(ts, attachment_storage_paths)
        return _text(client.update_draft(
            draft_id=draft_id,
            to=to, cc=cc, bcc=bcc, subject=subject,
            body_text=body_text, body_html=body_html,
            attachments=attachments,
        ))

    @server.tool()
    def send_draft(draft_id: str) -> List[TextContent]:
        """Send an existing draft."""
        return _text(_gmail_client(ts).send_draft(draft_id))

    @server.tool()
    def delete_draft(draft_id: str) -> List[TextContent]:
        """Delete a draft."""
        _gmail_client(ts).delete_draft(draft_id)
        return _text({"deleted": draft_id})

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------
    @server.tool()
    def list_labels() -> List[TextContent]:
        """List all labels (system and user)."""
        return _text(_gmail_client(ts).list_labels())

    @server.tool()
    def create_label(
        name: str,
        label_list_visibility: str = "labelShow",
        message_list_visibility: str = "show",
    ) -> List[TextContent]:
        """Create a user label."""
        return _text(_gmail_client(ts).create_label(
            name=name,
            label_list_visibility=label_list_visibility,
            message_list_visibility=message_list_visibility,
        ))

    @server.tool()
    def delete_label(label_id: str) -> List[TextContent]:
        """Delete a user label."""
        _gmail_client(ts).delete_label(label_id)
        return _text({"deleted": label_id})

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------
    @server.tool()
    def download_attachment(
        message_id: str,
        attachment_id: str,
        file_name: Optional[str] = None,
    ) -> List[TextContent]:
        """Download an attachment and upload it to Tool Store storage."""
        client = _gmail_client(ts)
        content, meta = client.get_attachment(message_id=message_id, attachment_id=attachment_id)
        target_name = file_name or (meta or {}).get("filename") or f"attachment-{attachment_id}"
        content_type = (meta or {}).get("mime_type") or "application/octet-stream"
        info = ts.upload_file(file_name=target_name, content=content, content_type=content_type)
        return _text({
            "storage": info,
            "attachment": {
                "message_id": message_id,
                "attachment_id": attachment_id,
                "file_name": target_name,
                "content_type": content_type,
                "size": len(content),
            },
        })

    return server


def main() -> None:
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
