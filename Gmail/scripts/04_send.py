"""04 — Send a real email.

⚠️  Side effect: sends ONE real email from the authenticated account to
    `GMAIL_TEST_RECIPIENT` (defaults to lilua.brainerhub@gmail.com).

The sent message id and threadId are saved in shared state so later scripts
(05 reply/forward, 06 trash/untrash) can reuse them.
"""

from _common import (
    TARGET_EMAIL,
    assert_ok,
    get_client,
    save_state,
    section,
    step,
)

SUBJECT = "test gmail tool via script"
BODY = "test gmail tool via script"


def main() -> int:
    client = get_client()

    section("send_message")
    step(f"sending to {TARGET_EMAIL} subject='{SUBJECT}'")
    result = client.send_message(
        to=TARGET_EMAIL,
        subject=SUBJECT,
        body_text=BODY,
    )

    message_id = result.get("id")
    thread_id = result.get("threadId")
    label_ids = result.get("labelIds") or []
    assert_ok(bool(message_id), "send returned a message id")
    assert_ok(bool(thread_id), "send returned a threadId")
    assert_ok("SENT" in label_ids, "message has SENT label")
    print(f"   message_id={message_id}")
    print(f"   thread_id={thread_id}")
    print(f"   labels={label_ids}")

    save_state("sent_message_id", message_id)
    save_state("sent_thread_id", thread_id)
    save_state("sent_to", TARGET_EMAIL)

    section("verify by fetching the sent message back")
    full = client.get_message(message_id)
    parsed = full.get("parsed") or {}
    assert_ok(parsed.get("subject") == SUBJECT, "subject round-trips correctly")
    assert_ok(parsed.get("from") is not None, "From header populated by Gmail")
    has_text = bool(parsed.get("body_text"))
    assert_ok(has_text, "text body present after send")
    print(f"   has_text={has_text}")

    section("04 — DONE")
    print(f"Sent 1 real email to {TARGET_EMAIL}. State saved for scripts 05/06.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
