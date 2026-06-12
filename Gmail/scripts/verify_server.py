"""Step A — Verify Gmail/server.py registers all expected MCP tools.

Imports the server module, calls `create_server()`, then asks the FastMCP instance
to list its registered tools. Asserts that the set of names matches what we expect,
and prints each tool's name and one-line description.

Pure introspection — no network calls happen (Gmail API or Tool Store).
"""

import asyncio
import os
import sys

_GMAIL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _GMAIL_DIR)

from server import create_server


EXPECTED_TOOLS = {
    "get_profile",
    "list_messages",
    "get_message",
    "get_thread",
    "send_message",
    "reply_to_message",
    "forward_message",
    "trash_message",
    "untrash_message",
    "delete_message",
    "modify_message_labels",
    "list_drafts",
    "get_draft",
    "create_draft",
    "update_draft",
    "send_draft",
    "delete_draft",
    "list_labels",
    "create_label",
    "delete_label",
    "download_attachment",
}


async def main() -> int:
    print("\n=== building server ===")
    server = create_server()
    print(f"   FastMCP instance: {server.name!r}")

    print("\n=== listing registered tools ===")
    tools = await server.list_tools()
    print(f"   total tools registered: {len(tools)}\n")

    found = set()
    for tool in sorted(tools, key=lambda t: t.name):
        found.add(tool.name)
        desc_first_line = (tool.description or "").strip().splitlines()[0] if tool.description else ""
        print(f"   - {tool.name}")
        if desc_first_line:
            print(f"       {desc_first_line}")

    print("\n=== verifying against expected set ===")
    missing = EXPECTED_TOOLS - found
    extra = found - EXPECTED_TOOLS

    if missing:
        sys.stderr.write(f"   FAIL: missing tools: {sorted(missing)}\n")
    if extra:
        sys.stderr.write(f"   FAIL: extra tools (not in expected set): {sorted(extra)}\n")

    if not missing and not extra:
        print(f"   PASS: all {len(EXPECTED_TOOLS)} expected tools are registered.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
