import base64
from email.message import EmailMessage
from email.utils import getaddresses
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailClient:
    """Minimal Gmail API v1 client using a bearer access token.

    Performs direct REST calls against `users/me` endpoints with an access token
    obtained via Tool Store activation. Token refresh is the caller's responsibility.

    Public methods are grouped:
        - Profile
        - Messages (list, get, send, reply, forward, trash/untrash/delete, modify labels)
        - Threads (get)
        - Drafts (list, get, create, update, send, delete)
        - Labels (list, create, delete)
        - Attachments (get, helper to parse from a message)
    """

    def __init__(self, access_token: str) -> None:
        if not access_token:
            raise ValueError("access_token is required")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {access_token}"})

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        url = f"{GMAIL_BASE}{path}"
        resp = self.session.request(method, url, params=params, json=json_body, timeout=timeout)
        if not resp.ok:
            raise RuntimeError(f"Gmail {method} {path} failed: {resp.status_code} {resp.text}")
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    def get_profile(self) -> Dict[str, Any]:
        """Return the authenticated user's email address and counters."""
        return self._request("GET", "/profile")

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------
    def list_messages(
        self,
        q: Optional[str] = None,
        label_ids: Optional[List[str]] = None,
        max_results: int = 50,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List or search messages. Returns ids only; call `get_message` for content."""
        if max_results <= 0 or max_results > 500:
            raise ValueError("max_results must be between 1 and 500")
        params: Dict[str, Any] = {"maxResults": max_results}
        if q:
            params["q"] = q
        if label_ids:
            params["labelIds"] = label_ids
        if page_token:
            params["pageToken"] = page_token
        return self._request("GET", "/messages", params=params)

    def get_message(self, message_id: str, fmt: str = "full") -> Dict[str, Any]:
        """Return a message with parsed headers, body parts, and attachment metadata.

        The Gmail response is augmented with `parsed` containing:
            - headers: dict of common headers (From, To, Cc, Subject, Date, Message-ID, etc.)
            - body_text, body_html: best-effort decoded bodies
            - attachments: list of {filename, mime_type, attachment_id, size}
        """
        if not message_id:
            raise ValueError("message_id is required")
        raw = self._request("GET", f"/messages/{message_id}", params={"format": fmt})
        raw["parsed"] = self._parse_message(raw)
        return raw

    def send_message(
        self,
        to: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        subject: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a message. Recipients are comma-separated strings.

        `attachments` items must be dicts with: file_name, content_bytes, content_type.
        """
        if not to:
            raise ValueError("to is required")
        mime = self._build_mime(
            to=to,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            in_reply_to=in_reply_to,
            references=references,
        )
        payload: Dict[str, Any] = {"raw": self._encode_raw(mime)}
        if thread_id:
            payload["threadId"] = thread_id
        return self._request("POST", "/messages/send", json_body=payload)

    def reply_to_message(
        self,
        message_id: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Reply to a message, preserving threading.

        Reuses the original Subject (prefixed with "Re: " when missing), and inherits
        From/Reply-To as the To recipient. Sets `In-Reply-To`, `References`, and `threadId`.
        """
        if not message_id:
            raise ValueError("message_id is required")
        original = self.get_message(message_id, fmt="metadata")
        headers = self._headers_dict(original.get("payload", {}).get("headers", []))

        reply_to = headers.get("Reply-To") or headers.get("From")
        if not reply_to:
            raise RuntimeError("Original message has no From/Reply-To header to reply to.")

        original_subject = headers.get("Subject", "")
        subject = original_subject if original_subject.lower().startswith("re:") else f"Re: {original_subject}".strip()

        original_msg_id = headers.get("Message-ID") or headers.get("Message-Id")
        references_chain = headers.get("References", "")
        new_references = f"{references_chain} {original_msg_id}".strip() if original_msg_id else references_chain

        return self.send_message(
            to=reply_to,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            thread_id=original.get("threadId"),
            in_reply_to=original_msg_id,
            references=new_references or None,
        )

    def forward_message(
        self,
        message_id: str,
        to: str,
        additional_text: Optional[str] = None,
        additional_html: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Forward a message to new recipients with an optional prefix note."""
        if not message_id:
            raise ValueError("message_id is required")
        if not to:
            raise ValueError("to is required")

        original = self.get_message(message_id, fmt="full")
        headers = self._headers_dict(original.get("payload", {}).get("headers", []))
        parsed = original.get("parsed", {})

        original_subject = headers.get("Subject", "")
        subject = original_subject if original_subject.lower().startswith("fwd:") else f"Fwd: {original_subject}".strip()

        forward_header = (
            "---------- Forwarded message ----------\n"
            f"From: {headers.get('From', '')}\n"
            f"Date: {headers.get('Date', '')}\n"
            f"Subject: {original_subject}\n"
            f"To: {headers.get('To', '')}\n\n"
        )

        body_text = (additional_text + "\n\n" if additional_text else "") + forward_header + (parsed.get("body_text") or "")
        body_html = None
        if additional_html or parsed.get("body_html"):
            html_intro = (additional_html + "<br><br>" if additional_html else "")
            html_quote = (
                "<div>---------- Forwarded message ----------<br>"
                f"<b>From:</b> {headers.get('From', '')}<br>"
                f"<b>Date:</b> {headers.get('Date', '')}<br>"
                f"<b>Subject:</b> {original_subject}<br>"
                f"<b>To:</b> {headers.get('To', '')}<br><br>"
                f"{parsed.get('body_html') or ''}"
                "</div>"
            )
            body_html = html_intro + html_quote

        return self.send_message(
            to=to,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

    def trash_message(self, message_id: str) -> Dict[str, Any]:
        if not message_id:
            raise ValueError("message_id is required")
        return self._request("POST", f"/messages/{message_id}/trash")

    def untrash_message(self, message_id: str) -> Dict[str, Any]:
        if not message_id:
            raise ValueError("message_id is required")
        return self._request("POST", f"/messages/{message_id}/untrash")

    def delete_message(self, message_id: str) -> None:
        if not message_id:
            raise ValueError("message_id is required")
        self._request("DELETE", f"/messages/{message_id}")

    def modify_message_labels(
        self,
        message_id: str,
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not message_id:
            raise ValueError("message_id is required")
        if not add_label_ids and not remove_label_ids:
            raise ValueError("Provide at least one of add_label_ids or remove_label_ids")
        body: Dict[str, Any] = {}
        if add_label_ids:
            body["addLabelIds"] = add_label_ids
        if remove_label_ids:
            body["removeLabelIds"] = remove_label_ids
        return self._request("POST", f"/messages/{message_id}/modify", json_body=body)

    # ------------------------------------------------------------------
    # Threads
    # ------------------------------------------------------------------
    def get_thread(self, thread_id: str) -> Dict[str, Any]:
        if not thread_id:
            raise ValueError("thread_id is required")
        return self._request("GET", f"/threads/{thread_id}", params={"format": "full"})

    # ------------------------------------------------------------------
    # Drafts
    # ------------------------------------------------------------------
    def list_drafts(
        self,
        q: Optional[str] = None,
        max_results: int = 50,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        if max_results <= 0 or max_results > 500:
            raise ValueError("max_results must be between 1 and 500")
        params: Dict[str, Any] = {"maxResults": max_results}
        if q:
            params["q"] = q
        if page_token:
            params["pageToken"] = page_token
        return self._request("GET", "/drafts", params=params)

    def get_draft(self, draft_id: str) -> Dict[str, Any]:
        if not draft_id:
            raise ValueError("draft_id is required")
        return self._request("GET", f"/drafts/{draft_id}", params={"format": "full"})

    def create_draft(
        self,
        to: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        subject: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        mime = self._build_mime(
            to=to or "",
            cc=cc,
            bcc=bcc,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        )
        message: Dict[str, Any] = {"raw": self._encode_raw(mime)}
        if thread_id:
            message["threadId"] = thread_id
        return self._request("POST", "/drafts", json_body={"message": message})

    def update_draft(
        self,
        draft_id: str,
        to: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        subject: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not draft_id:
            raise ValueError("draft_id is required")
        mime = self._build_mime(
            to=to or "",
            cc=cc,
            bcc=bcc,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        )
        message: Dict[str, Any] = {"raw": self._encode_raw(mime)}
        if thread_id:
            message["threadId"] = thread_id
        return self._request("PUT", f"/drafts/{draft_id}", json_body={"message": message})

    def send_draft(self, draft_id: str) -> Dict[str, Any]:
        if not draft_id:
            raise ValueError("draft_id is required")
        return self._request("POST", "/drafts/send", json_body={"id": draft_id})

    def delete_draft(self, draft_id: str) -> None:
        if not draft_id:
            raise ValueError("draft_id is required")
        self._request("DELETE", f"/drafts/{draft_id}")

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------
    def list_labels(self) -> Dict[str, Any]:
        return self._request("GET", "/labels")

    def create_label(
        self,
        name: str,
        label_list_visibility: str = "labelShow",
        message_list_visibility: str = "show",
    ) -> Dict[str, Any]:
        if not name:
            raise ValueError("name is required")
        body = {
            "name": name,
            "labelListVisibility": label_list_visibility,
            "messageListVisibility": message_list_visibility,
        }
        return self._request("POST", "/labels", json_body=body)

    def delete_label(self, label_id: str) -> None:
        if not label_id:
            raise ValueError("label_id is required")
        self._request("DELETE", f"/labels/{label_id}")

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------
    def get_attachment(self, message_id: str, attachment_id: str) -> Tuple[bytes, Optional[Dict[str, Any]]]:
        """Fetch attachment bytes plus the matching attachment metadata from the parent message."""
        if not message_id:
            raise ValueError("message_id is required")
        if not attachment_id:
            raise ValueError("attachment_id is required")

        data = self._request("GET", f"/messages/{message_id}/attachments/{attachment_id}")
        b64 = data.get("data", "")
        if not b64:
            raise RuntimeError("Attachment payload was empty.")
        content = base64.urlsafe_b64decode(self._pad_b64url(b64))

        meta: Optional[Dict[str, Any]] = None
        try:
            parent = self.get_message(message_id)
            for att in parent.get("parsed", {}).get("attachments", []):
                if att.get("attachment_id") == attachment_id:
                    meta = att
                    break
        except Exception:
            meta = None
        return content, meta

    # ==================================================================
    # Private helpers
    # ==================================================================
    @staticmethod
    def _encode_raw(message: EmailMessage) -> str:
        """Base64url-encode an EmailMessage as required by Gmail's `raw` field."""
        return base64.urlsafe_b64encode(bytes(message)).decode("ascii").rstrip("=")

    @staticmethod
    def _pad_b64url(s: str) -> str:
        return s + "=" * (-len(s) % 4)

    @staticmethod
    def _build_mime(
        to: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        subject: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> EmailMessage:
        """Build an RFC 5322 MIME message with optional HTML alternative and attachments."""
        msg = EmailMessage()
        if to:
            msg["To"] = to
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc
        if subject is not None:
            msg["Subject"] = subject
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = references

        # Body: support text-only, html-only, or multipart/alternative
        if body_text is None and body_html is None:
            msg.set_content("")
        elif body_html and body_text:
            msg.set_content(body_text)
            msg.add_alternative(body_html, subtype="html")
        elif body_html:
            msg.set_content(body_html, subtype="html")
        else:
            msg.set_content(body_text or "")

        for att in attachments or []:
            file_name = att.get("file_name") or "attachment"
            content_bytes = att.get("content_bytes")
            content_type = att.get("content_type") or "application/octet-stream"
            if not isinstance(content_bytes, (bytes, bytearray)):
                raise ValueError(f"Attachment '{file_name}' is missing content_bytes")
            maintype, _, subtype = content_type.partition("/")
            msg.add_attachment(
                bytes(content_bytes),
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=file_name,
            )
        return msg

    @staticmethod
    def _headers_dict(headers: Iterable[Dict[str, str]]) -> Dict[str, str]:
        """Convert Gmail's header list into a dict (last value wins, like RFC 5322)."""
        out: Dict[str, str] = {}
        for h in headers or []:
            name = h.get("name")
            value = h.get("value")
            if name and value is not None:
                out[name] = value
        return out

    @classmethod
    def _parse_message(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Extract headers, plain/HTML body, and attachment metadata from a Gmail message."""
        payload = raw.get("payload", {}) or {}
        headers = cls._headers_dict(payload.get("headers", []))
        body_text, body_html, attachments = cls._walk_parts(payload)
        return {
            "headers": headers,
            "from": headers.get("From"),
            "to": [addr for _, addr in getaddresses([headers.get("To", "")])] if headers.get("To") else [],
            "cc": [addr for _, addr in getaddresses([headers.get("Cc", "")])] if headers.get("Cc") else [],
            "subject": headers.get("Subject"),
            "date": headers.get("Date"),
            "snippet": raw.get("snippet"),
            "body_text": body_text,
            "body_html": body_html,
            "attachments": attachments,
        }

    @classmethod
    def _walk_parts(cls, part: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], List[Dict[str, Any]]]:
        """Depth-first traversal of a MIME payload returning (text, html, attachments)."""
        body_text: Optional[str] = None
        body_html: Optional[str] = None
        attachments: List[Dict[str, Any]] = []

        mime_type = part.get("mimeType", "")
        filename = part.get("filename") or ""
        body = part.get("body", {}) or {}
        sub_parts = part.get("parts") or []

        if filename:
            attachments.append({
                "filename": filename,
                "mime_type": mime_type,
                "attachment_id": body.get("attachmentId"),
                "size": body.get("size"),
            })
        elif mime_type == "text/plain" and body.get("data"):
            body_text = cls._decode_part_data(body["data"])
        elif mime_type == "text/html" and body.get("data"):
            body_html = cls._decode_part_data(body["data"])

        for child in sub_parts:
            t, h, atts = cls._walk_parts(child)
            body_text = body_text or t
            body_html = body_html or h
            attachments.extend(atts)

        return body_text, body_html, attachments

    @staticmethod
    def _decode_part_data(data: str) -> str:
        try:
            padded = data + "=" * (-len(data) % 4)
            return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
        except Exception:
            return ""
