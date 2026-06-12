"""07 — Attachment download.

Searches for the first message with `has:attachment`, picks the first non-empty
attachment, downloads it via get_attachment, writes the bytes to /tmp/, and
checks that the on-disk size matches the metadata size.

No Gmail writes happen.
"""

import os

from _common import assert_ok, get_client, section, step


def main() -> int:
    client = get_client()

    section("locate a message with an attachment")
    listing = client.list_messages(q="has:attachment", max_results=10)
    refs = listing.get("messages") or []
    if not refs:
        print("   no messages with attachments found. Send yourself one and retry.")
        return 0

    target_id = None
    target_attachment = None
    for ref in refs:
        message_id = ref["id"]
        full = client.get_message(message_id)
        attachments = (full.get("parsed") or {}).get("attachments") or []
        for att in attachments:
            if att.get("attachment_id") and (att.get("size") or 0) > 0:
                target_id = message_id
                target_attachment = att
                break
        if target_id:
            break

    if not target_id or not target_attachment:
        print("   found messages flagged has:attachment but none had inline attachment_id+size.")
        return 0

    filename = target_attachment.get("filename") or "attachment.bin"
    expected_size = target_attachment.get("size") or 0
    print(f"   message_id={target_id}")
    print(f"   filename={filename!r}  size={expected_size}  mime={target_attachment.get('mime_type')!r}")

    section("get_attachment")
    step("downloading bytes")
    content, meta = client.get_attachment(target_id, target_attachment["attachment_id"])
    assert_ok(isinstance(content, (bytes, bytearray)) and len(content) > 0, "non-empty bytes returned")
    if expected_size:
        assert_ok(
            len(content) == expected_size,
            f"downloaded size matches metadata ({len(content)} == {expected_size})",
        )
    if meta is not None:
        print("   PASS: attachment metadata resolved from parent message")
    else:
        print("   INFO: parent-message metadata lookup returned None (Gmail rotates attachment ids; expected).")

    section("write to /tmp")
    safe_name = filename.replace("/", "_").replace("\\", "_")
    out_path = os.path.join("/tmp", f"gmail_test_{safe_name}")
    with open(out_path, "wb") as f:
        f.write(content)
    on_disk = os.path.getsize(out_path)
    assert_ok(on_disk == len(content), f"file written to {out_path} ({on_disk} bytes)")

    section("07 — DONE")
    print(f"Attachment download PASS. File at {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
