"""03 — run_cli_command.

Exercises successful argv runs and basic failure cases.
Uses host binaries only (node/python/echo) — no network installs.
"""

from __future__ import annotations

from _common import (
    CliRuntimeError,
    assert_ok,
    check_binary,
    pretty,
    run_cli_command,
    section,
    step,
)


def main() -> int:
    section("run_cli success with a local binary")
    if check_binary("node")["available"]:
        result = run_cli_command(["node", "-v"], timeout_seconds=30)
        binary_label = "node"
    else:
        result = run_cli_command(["python3", "-c", "print('ok')"], timeout_seconds=30)
        binary_label = "python3"
    pretty(result)
    assert_ok(result["ok"] is True, f"{binary_label} command exited 0")
    assert_ok(result["exit_code"] == 0, "exit_code is 0")
    assert_ok(bool(result["stdout"].strip()), "stdout is non-empty")

    section("run_cli rejects empty argv")
    try:
        run_cli_command([])
        assert_ok(False, "empty argv should raise")
    except CliRuntimeError as exc:
        assert_ok("non-empty" in str(exc).lower() or "empty" in str(exc).lower(), f"rejected empty argv: {exc}")

    section("run_cli rejects path-like binary")
    try:
        run_cli_command(["/usr/bin/node", "-v"])
        assert_ok(False, "path binary should raise")
    except CliRuntimeError as exc:
        assert_ok("bare name" in str(exc).lower() or "path" in str(exc).lower(), f"rejected path binary: {exc}")

    section("run_cli rejects missing binary")
    try:
        run_cli_command(["definitely-not-a-real-cli-binary-xyz"])
        assert_ok(False, "missing binary should raise")
    except CliRuntimeError as exc:
        assert_ok("not found" in str(exc).lower(), f"missing binary error: {exc}")

    section("run_cli captures non-zero exit")
    # Use a binary that exists but fails: python3 -c 'raise SystemExit(7)'
    if check_binary("python3")["available"]:
        failed = run_cli_command(["python3", "-c", "raise SystemExit(7)"], timeout_seconds=30)
        pretty(failed)
        assert_ok(failed["ok"] is False, "non-zero exit marked not ok")
        assert_ok(failed["exit_code"] == 7, "exit_code preserved")
    else:
        step("python3 missing — skipped non-zero exit check")

    print("\nAll 03 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
