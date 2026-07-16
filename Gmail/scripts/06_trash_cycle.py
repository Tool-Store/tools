"""06 — Trash + untrash cycle.

Uses the message sent by script 04 (`sent_message_id` in shared state).
By default, net side effect: zero. The message is trashed and then untrashed.

Set GMAIL_TEST_KEEP_TRASHED=1 to stop after the trash step, so the message stays
in Trash (the untrash + delete_message steps are skipped).

Note: permanent `delete_message` is NOT exercised because our gmail.modify scope
returns 403 for it. That requires the full `https://mail.google.com/` scope.
"""

import os

from _common import (
    assert_ok,
    get_client,
    require_state,
    section,
    step,
)


def main() -> int:
    client = get_client()
    message_id = require_state("sent_message_id", "Run scripts/04_send.py first.")
    keep_trashed = os.environ.get("GMAIL_TEST_KEEP_TRASHED") == "1"

    section("baseline labels")
    before = client.get_message(message_id, fmt="minimal")
    labels_before = set(before.get("labelIds") or [])
    print(f"   labels_before={sorted(labels_before)}")
    assert_ok("TRASH" not in labels_before, "message is NOT in trash before test")

    section("trash_message")
    step(f"trashing {message_id}")
    trashed = client.trash_message(message_id)
    trashed_labels = set(trashed.get("labelIds") or [])
    assert_ok("TRASH" in trashed_labels, "TRASH label present after trash_message")

    if keep_trashed:
        section("untrash_message (SKIPPED)")
        print(f"   GMAIL_TEST_KEEP_TRASHED=1 set; leaving message {message_id} in Trash.")
        print("   Open https://mail.google.com/mail/u/0/#trash to view it.")
        section("06 — DONE")
        print("Message moved to Trash and left there.")
        return 0

    section("untrash_message")
    step(f"untrashing {message_id}")
    untrashed = client.untrash_message(message_id)
    untrashed_labels = set(untrashed.get("labelIds") or [])
    assert_ok("TRASH" not in untrashed_labels, "TRASH label gone after untrash_message")

    section("verify message is back to its original state")
    after = client.get_message(message_id, fmt="minimal")
    labels_after = set(after.get("labelIds") or [])
    print(f"   labels_after={sorted(labels_after)}")
    assert_ok("TRASH" not in labels_after, "message no longer in trash")

    section("delete_message (intentionally skipped)")
    print("   skipped: requires https://mail.google.com/ scope; current scope is gmail.modify.")
    print("   permanent delete would return 403 Insufficient Permission. Behaviour documented.")

    section("06 — DONE")
    print("Trash/untrash cycle PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
