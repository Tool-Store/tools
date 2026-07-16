"""01 — Read-only verification.

Exercises every read-only GmailClient method:
    get_profile, list_messages (basic / with q / with label filter),
    get_message, get_thread, list_labels, list_drafts.

Performs no writes. Saves the latest message id into the shared state so later
scripts can reuse it if needed.
"""

from _common import assert_ok, get_client, save_state, section, step


def main() -> int:
    client = get_client()

    section("get_profile")
    profile = client.get_profile()
    assert_ok(bool(profile.get("emailAddress")), "profile has emailAddress")
    print(
        f"   email={profile['emailAddress']} "
        f"messages={profile.get('messagesTotal')} "
        f"threads={profile.get('threadsTotal')}"
    )
    save_state("self_email", profile["emailAddress"])

    section("list_messages (basic, max=5)")
    listing = client.list_messages(max_results=5)
    messages = listing.get("messages") or []
    assert_ok(len(messages) > 0, "at least one message returned")
    first_id = messages[0]["id"]
    first_thread_id = messages[0].get("threadId")
    save_state("first_message_id", first_id)
    if first_thread_id:
        save_state("first_thread_id", first_thread_id)
    print(f"   first id={first_id}")

    section("list_messages with q='is:inbox', max=3")
    inbox_listing = client.list_messages(q="in:inbox", max_results=3)
    assert_ok("messages" in inbox_listing or inbox_listing == {}, "query returned a valid payload")
    inbox_count = len(inbox_listing.get("messages") or [])
    print(f"   matched={inbox_count}")

    section("list_messages with label_ids=['INBOX'], max=3")
    label_listing = client.list_messages(label_ids=["INBOX"], max_results=3)
    assert_ok("messages" in label_listing or label_listing == {}, "label filter returned a valid payload")
    print(f"   matched={len(label_listing.get('messages') or [])}")

    section("get_message")
    step(f"fetching full message {first_id}")
    full = client.get_message(first_id)
    parsed = full.get("parsed") or {}
    assert_ok(bool(parsed.get("headers")), "parsed.headers populated")
    assert_ok(parsed.get("subject") is not None, "parsed.subject extracted")
    assert_ok(parsed.get("from") is not None, "parsed.from extracted")
    body_text = parsed.get("body_text")
    body_html = parsed.get("body_html")
    snippet = full.get("snippet") or ""
    assert_ok(any([body_text, body_html, snippet]), "message has some body or snippet")
    print(f"   subject={parsed.get('subject')!r}")
    print(f"   from={parsed.get('from')!r}")
    print(f"   attachments={len(parsed.get('attachments') or [])}")

    section("get_thread")
    thread_id = full.get("threadId") or first_thread_id
    if thread_id:
        step(f"fetching thread {thread_id}")
        thread = client.get_thread(thread_id)
        thread_messages = thread.get("messages") or []
        assert_ok(len(thread_messages) > 0, "thread returned at least one message")
        print(f"   thread has {len(thread_messages)} message(s)")
    else:
        print("   (no threadId on first message; skipping)")

    section("list_labels")
    labels_resp = client.list_labels()
    labels = labels_resp.get("labels") or []
    assert_ok(len(labels) > 0, "labels list non-empty")
    names = {l.get("name") for l in labels}
    for required in ("INBOX", "SENT", "DRAFT"):
        assert_ok(required in names, f"system label {required} present")

    section("list_drafts")
    drafts_resp = client.list_drafts(max_results=3)
    assert_ok("drafts" in drafts_resp or drafts_resp == {}, "drafts listing returned a valid payload")
    print(f"   drafts in account={drafts_resp.get('resultSizeEstimate', 'n/a')}")

    section("01 — DONE")
    print("All read-only assertions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
