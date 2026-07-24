"""Step A — Verify cli-runner/server.py registers all expected MCP tools.

Pure introspection — no installs or subprocess commands beyond importing the server.
"""

from __future__ import annotations

import asyncio
import os
import sys

_CLI_RUNNER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _CLI_RUNNER_DIR)

from server import create_server

EXPECTED_TOOLS = {
    "get_skill_install_status",
    "check_cli_binary",
    "install_skill_cli",
    "run_cli",
}


async def main() -> int:
    print("\n=== building server ===")
    server = create_server()
    print(f"   FastMCP instance: {server.name!r}")

    print("\n=== listing registered tools ===")
    tools = await server.list_tools()
    print(f"   total tools registered: {len(tools)}\n")

    found: set[str] = set()
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
