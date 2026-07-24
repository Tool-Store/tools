"""MCP server for the shared CLI Runner tool."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

from cli_runtime import (
    CliRuntimeError,
    check_binary,
    get_install_status,
    install_skill_runtime,
    run_cli_command,
)


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO))


def _text(payload: Any) -> list[TextContent]:
    if isinstance(payload, (dict, list)):
        body = json.dumps(payload, indent=2, default=str)
    else:
        body = str(payload)
    return [TextContent(type="text", text=body)]


def create_server() -> FastMCP:
    """Create the MCP server and register CLI runner tools."""
    load_dotenv()
    _setup_logging()
    server = FastMCP(
        "cli-runner",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8000")),
    )

    @server.tool()
    def get_skill_install_status(skill_slug: str) -> list[TextContent]:
        """Return whether a skill's CLI runtime was already installed in this container."""
        try:
            return _text(get_install_status(skill_slug))
        except CliRuntimeError as exc:
            raise RuntimeError(str(exc)) from exc

    @server.tool()
    def check_cli_binary(binary: str) -> list[TextContent]:
        """Check whether a binary is available on PATH."""
        try:
            return _text(check_binary(binary))
        except CliRuntimeError as exc:
            raise RuntimeError(str(exc)) from exc

    @server.tool()
    def install_skill_cli(
        skill_slug: str,
        bins: Optional[list[str]] = None,
        install_steps: Optional[list[str]] = None,
        timeout_seconds: int = 300,
        force: bool = False,
    ) -> list[TextContent]:
        """Install a skill's CLI deps once in this container. Skips if already installed."""
        try:
            return _text(
                install_skill_runtime(
                    skill_slug,
                    bins=bins,
                    install_steps=install_steps,
                    timeout_seconds=timeout_seconds,
                    force=force,
                )
            )
        except CliRuntimeError as exc:
            raise RuntimeError(str(exc)) from exc

    @server.tool()
    def run_cli(
        argv: list[str],
        timeout_seconds: int = 120,
    ) -> list[TextContent]:
        """Run a CLI command as an argv list (no shell). Example: ["agent-browser", "open", "https://example.com"]."""
        try:
            return _text(run_cli_command(argv, timeout_seconds=timeout_seconds))
        except CliRuntimeError as exc:
            raise RuntimeError(str(exc)) from exc

    return server


def main() -> None:
    server = create_server()
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    server.run(transport=transport)


if __name__ == "__main__":
    main()
