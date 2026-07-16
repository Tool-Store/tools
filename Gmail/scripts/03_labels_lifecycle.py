"""03 — Labels lifecycle.

create_label → modify_message_labels(add) → modify_message_labels(remove) → delete_label.

Net side effect: zero. The label is created and removed. The test message has the
label briefly applied and then removed (no labels stick to it permanently).
"""

from _common import assert_ok, get_client, now_marker, section, step


def main() -> int:
    client = get_client()

    section("list_labels (baseline)")
    baseline = client.list_labels().get("labels") or []
    baseline_names = {l.get("name") for l in baseline}
    print(f"   {len(baseline)} labels exist before test")

    section("create_label")
    name = now_marker("GmailToolTestLabel")
    step(f"creating label '{name}'")
    created = client.create_label(name)
    label_id = created.get("id")
    assert_ok(bool(label_id), "create_label returned an id")
    assert_ok(created.get("name") == name, "returned label has expected name")
    print(f"   label_id={label_id}")

    section("list_labels (after create)")
    after_create = client.list_labels().get("labels") or []
    after_names = {l.get("name") for l in after_create}
    assert_ok(name in after_names, "new label appears in list_labels")
    assert_ok(name not in baseline_names, "new label was not present before")

    section("modify_message_labels — add")
    listing = client.list_messages(max_results=1)
    message_refs = listing.get("messages") or []
    if not message_refs:
        print("   skipped: account has no messages to apply a label to")
    else:
        message_id = message_refs[0]["id"]
        step(f"adding {name} to message {message_id}")
        result_add = client.modify_message_labels(message_id, add_label_ids=[label_id])
        assert_ok(label_id in (result_add.get("labelIds") or []), "label appears in message.labelIds after add")

        section("modify_message_labels — remove")
        step(f"removing {name} from message {message_id}")
        result_remove = client.modify_message_labels(message_id, remove_label_ids=[label_id])
        assert_ok(label_id not in (result_remove.get("labelIds") or []), "label removed from message.labelIds")

    section("delete_label")
    client.delete_label(label_id)
    final = client.list_labels().get("labels") or []
    final_names = {l.get("name") for l in final}
    assert_ok(name not in final_names, "label gone from list_labels after delete")

    section("03 — DONE")
    print("Label lifecycle PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
