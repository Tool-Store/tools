"""02 — Install lifecycle.

Exercises:
    install_skill_runtime (first install, skip on second call, force reinstall)
    get_install_status

Uses harmless install steps (echo / true) and bins already on PATH (node) when available.
Writes only to the temp CLI_RUNNER_STATE_PATH file.
"""

from __future__ import annotations

from _common import (
    assert_ok,
    check_binary,
    get_install_status,
    install_skill_runtime,
    pretty,
    reset_install_state,
    section,
    step,
)

TEST_SLUG = "cli-runner-selftest"


def main() -> int:
    reset_install_state()

    node = check_binary("node")
    bins = ["node"] if node["available"] else []
    steps = ["echo cli-runner-install-ok"]
    if not bins:
        step("node missing — install will only run echo steps (no bin verification)")

    section("first install")
    first = install_skill_runtime(
        TEST_SLUG,
        bins=bins,
        install_steps=steps,
        timeout_seconds=30,
    )
    pretty(first)
    assert_ok(first["skipped"] is False, "first install not skipped")
    assert_ok(first["skill_slug"] == TEST_SLUG, "slug matches")
    assert_ok(len(first["steps_run"]) == 1, "one install step ran")
    assert_ok(first["steps_run"][0]["ok"] is True, "echo step succeeded")

    section("status after install")
    status = get_install_status(TEST_SLUG)
    pretty(status)
    assert_ok(status["installed"] is True, "skill marked installed")

    section("second install (should skip)")
    second = install_skill_runtime(
        TEST_SLUG,
        bins=bins,
        install_steps=steps,
        timeout_seconds=30,
    )
    pretty(second)
    assert_ok(second["skipped"] is True, "second install skipped")
    assert_ok(second.get("reason") == "already_installed", "skip reason is already_installed")
    assert_ok(second["steps_run"] == [], "no steps re-run")

    section("force reinstall")
    forced = install_skill_runtime(
        TEST_SLUG,
        bins=bins,
        install_steps=steps,
        timeout_seconds=30,
        force=True,
    )
    pretty(forced)
    assert_ok(forced["skipped"] is False, "force install not skipped")
    assert_ok(len(forced["steps_run"]) == 1, "force re-ran install step")

    print("\nAll 02 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
