"""02 — Drafts lifecycle (create → get → update → list → delete).

By default, net side effect: zero (the draft is deleted at the end). Does not send anything.

Set GMAIL_TEST_KEEP_DRAFT=1 to skip the delete step, so the draft remains in your
Drafts folder for manual visual inspection in the Gmail UI.
"""

import os

from _common import (
    TARGET_EMAIL,
    assert_ok,
    get_client,
    section,
    step,
)

SUBJECT = "test gmail tool via script"
SUBJECT_UPDATED = "test gmail tool via script (updated)"
BODY = "test gmail tool via script"


def main() -> int:
    client = get_client()

    section("create_draft")
    step(f"creating draft to {TARGET_EMAIL} subject='{SUBJECT}'")
    created = client.create_draft(
        to=TARGET_EMAIL,
        subject=SUBJECT,
        body_text=BODY,
    )
    draft_id = created.get("id")
    inner_message_id = (created.get("message") or {}).get("id")
    assert_ok(bool(draft_id), "draft.id returned")
    assert_ok(bool(inner_message_id), "draft.message.id returned")
    print(f"   draft_id={draft_id} message_id={inner_message_id}")

    section("get_draft")
    fetched = client.get_draft(draft_id)
    assert_ok(fetched.get("id") == draft_id, "get_draft returns same id")
    message_payload = fetched.get("message") or {}
    headers = {h.get("name"): h.get("value") for h in (message_payload.get("payload", {}).get("headers") or [])}
    assert_ok(headers.get("Subject") == SUBJECT, "subject matches what we created")
    assert_ok(TARGET_EMAIL in (headers.get("To") or ""), "To header contains target email")

    section("update_draft")
    step(f"updating draft subject to '{SUBJECT_UPDATED}'")
    client.update_draft(
        draft_id,
        to=TARGET_EMAIL,
        subject=SUBJECT_UPDATED,
        body_text=BODY,
    )
    re_fetched = client.get_draft(draft_id)
    headers2 = {
        h.get("name"): h.get("value")
        for h in (re_fetched.get("message", {}).get("payload", {}).get("headers") or [])
    }
    assert_ok(headers2.get("Subject") == SUBJECT_UPDATED, "subject reflects update")

    section("list_drafts")
    listing = client.list_drafts(max_results=50)
    drafts = listing.get("drafts") or []
    found = any(d.get("id") == draft_id for d in drafts)
    assert_ok(found, "our draft appears in list_drafts")
    print(f"   total drafts visible in first page={len(drafts)}")

    keep_draft = os.environ.get("GMAIL_TEST_KEEP_DRAFT") == "1"

    if keep_draft:
        section("delete_draft (SKIPPED)")
        print(f"   GMAIL_TEST_KEEP_DRAFT=1 set; leaving draft {draft_id} in place.")
        print("   Open https://mail.google.com/mail/u/0/#drafts to view it.")
        print("   To clean up later, unset the env var and rerun this script,")
        print("   or delete the draft manually from the Gmail UI.")
    else:
        section("delete_draft")
        client.delete_draft(draft_id)
        try:
            client.get_draft(draft_id)
            assert_ok(False, "expected get_draft to fail after delete")
        except RuntimeError as exc:
            assert_ok("404" in str(exc) or "Not Found" in str(exc), "get_draft returns 404 after delete")

    section("02 — DONE")
    print("Draft lifecycle PASS. No emails sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
