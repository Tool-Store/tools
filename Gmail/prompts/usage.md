AI Usage Guidance

Purpose
- This tool manages Gmail messages, drafts, labels, and attachments for the authenticated user. Use it to read, search, send, reply, forward, organize, and download attachments. Attachments uploaded via send come from Tool Store storage.

General Guidance
- Prefer `list_messages` with Gmail `q` syntax to narrow results before calling `get_message`.
- Use `get_message` for full headers, plain/HTML bodies, and attachment metadata.
- For replies, always pass the original `message_id` to `reply_to_message` so threading is preserved.
- For attachments on send, upload files to Tool Store storage first, then pass `attachment_storage_paths`.
- For attachment downloads, use `download_attachment` with the `attachment_id` from `get_message`; the file is uploaded to Tool Store storage and the storage path is returned.

Gmail `q` syntax (most useful operators)
- `from:`, `to:`, `cc:`, `bcc:`, `subject:`
- `is:unread`, `is:read`, `is:starred`, `has:attachment`
- `label:<name>`, `in:inbox`, `in:trash`
- `after:YYYY/MM/DD`, `before:YYYY/MM/DD`, `newer_than:7d`
- Combine with parentheses and `OR`/`AND` (default is AND)

Actions
- list messages: Provide optional `q`, `label_ids`, `max_results` (default 50, max 500), `page_token`.
- get message: Provide `message_id`.
- get thread: Provide `thread_id`.
- send message: Provide `to`, optional `cc`, `bcc`, `subject`, `body_text`, `body_html`, `attachment_storage_paths` (list of Tool Store storage paths).
- reply to message: Provide `message_id`, `body_text` and/or `body_html`, optional `attachment_storage_paths`.
- forward message: Provide `message_id`, `to`, optional `additional_text`/`additional_html`.
- trash / untrash / delete message: Provide `message_id`.
- modify message labels: Provide `message_id`, optional `add_label_ids`, `remove_label_ids` (lists). Use this to mark read/unread (UNREAD), star (STARRED), archive (remove INBOX).
- list drafts / get draft / delete draft / send draft: Provide `draft_id` where relevant.
- create draft: Same fields as send_message; returns draft id.
- update draft: Provide `draft_id` plus replacement fields.
- list labels / create label / delete label: Provide `label_id` or label `name` as needed.
- download attachment: Provide `message_id`, `attachment_id`, optional `file_name`; returns Tool Store storage info.
- get profile: No input; returns email and counts.

Authentication
- If the action fails due to missing/expired credentials, the tool attempts an automatic refresh via the Tool Store endpoint when configured. Otherwise, prompt the user to run activation and re-connect their Google account.
