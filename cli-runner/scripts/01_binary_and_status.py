"""01 — Binary check + install status (read-only against the host PATH).

Exercises:
    check_binary, get_install_status

No installs. Safe to run anytime.
"""

from __future__ import annotations

from _common import assert_ok, check_binary, get_install_status, pretty, section, step


def main() -> int:
    section("check_binary('node')")
    node = check_binary("node")
    pretty(node)
    assert_ok(node["binary"] == "node", "binary name echoed")
    assert_ok("available" in node, "available flag present")
    if node["available"]:
        assert_ok(bool(node.get("path")), "path set when available")
    else:
        step("node not on PATH — later install/run scripts that need node may fail")

    section("check_binary('python') / 'python3'")
    py = check_binary("python3")
    if not py["available"]:
        py = check_binary("python")
    pretty(py)
    assert_ok(py["available"], "python or python3 is on PATH")

    section("get_install_status for unknown skill")
    status = get_install_status("not-installed-skill")
    pretty(status)
    assert_ok(status["skill_slug"] == "not-installed-skill", "slug echoed")
    assert_ok(status["installed"] is False, "unknown skill is not installed")

    print("\nAll 01 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
