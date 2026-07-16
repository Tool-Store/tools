"""05 — Reply + forward, using the message sent by script 04.

⚠️  Side effects: sends TWO real emails.
    - reply_to_message  → goes to the From of the original (the authenticated account itself,
                          because we sent the original from this account)
    - forward_message   → goes to GMAIL_TEST_RECIPIENT

Requires `sent_message_id` and `sent_thread_id` in shared state (created by 04_send.py).
"""

from _common import (
    TARGET_EMAIL,
    assert_ok,
    get_client,
    require_state,
    save_state,
    section,
    step,
)


BODY = "test gmail tool via script"


def main() -> int:
    client = get_client()
    original_id = require_state("sent_message_id", "Run scripts/04_send.py first.")
    original_thread_id = require_state("sent_thread_id", "Run scripts/04_send.py first.")

    section("reply_to_message")
    step(f"replying to {original_id}")
    reply = client.reply_to_message(
        message_id=original_id,
        body_text=BODY,
    )

    reply_id = reply.get("id")
    reply_thread = reply.get("threadId")
    assert_ok(bool(reply_id), "reply returned a message id")
    assert_ok(reply_thread == original_thread_id, "reply preserves original threadId")
    print(f"   reply_id={reply_id}  same_thread={reply_thread == original_thread_id}")

    section("verify reply headers preserve threading")
    reply_full = client.get_message(reply_id, fmt="metadata")
    reply_headers = {
        h.get("name"): h.get("value")
        for h in (reply_full.get("payload", {}).get("headers") or [])
    }
    subj = reply_headers.get("Subject") or ""
    in_reply_to = reply_headers.get("In-Reply-To") or ""
    references = reply_headers.get("References") or ""
    assert_ok(subj.lower().startswith("re:"), f"reply subject starts with 'Re:' (got: {subj!r})")
    assert_ok(bool(in_reply_to), "In-Reply-To header populated")
    assert_ok(bool(references), "References header populated")
    save_state("reply_message_id", reply_id)

    section("forward_message")
    step(f"forwarding {original_id} to {TARGET_EMAIL}")
    fwd = client.forward_message(
        message_id=original_id,
        to=TARGET_EMAIL,
        additional_text=BODY,
    )
    fwd_id = fwd.get("id")
    assert_ok(bool(fwd_id), "forward returned a message id")

    fwd_full = client.get_message(fwd_id, fmt="metadata")
    fwd_headers = {
        h.get("name"): h.get("value")
        for h in (fwd_full.get("payload", {}).get("headers") or [])
    }
    fwd_subj = fwd_headers.get("Subject") or ""
    fwd_to = fwd_headers.get("To") or ""
    assert_ok(fwd_subj.lower().startswith("fwd:"), f"forward subject starts with 'Fwd:' (got: {fwd_subj!r})")
    assert_ok(TARGET_EMAIL in fwd_to, "forward To header contains target email")
    save_state("forward_message_id", fwd_id)

    section("05 — DONE")
    print("Sent 1 reply and 1 forward. Threading and subject prefixes verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
