import logging
import os
from typing import Any, List, Optional

from dotenv import load_dotenv

import scraper
from toolstore_client import ToolStoreClient

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

JINA_SECRET_NAME = "JINA_API_KEY"


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO))


def _text(payload: Any) -> List[TextContent]:
    """Wrap a Python value as a single TextContent block for MCP responses."""
    return [TextContent(type="text", text=str(payload))]


def _jina_api_key() -> Optional[str]:
    """Return the user's optional Jina key from Tool Store activation secrets (env var for local dev)."""
    # Construct per call: the client captures the calling user's identity when created.
    ts = ToolStoreClient()
    if not ts.jwt:
        return os.getenv(JINA_SECRET_NAME) or None
    return ts.get_secrets().get(JINA_SECRET_NAME)


def create_server() -> FastMCP:
    """Create the MCP server and register Social Media Scraper tools."""
    load_dotenv()
    _setup_logging()
    server = FastMCP(
        "social-media-scraper",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8000")),
    )

    @server.tool()
    def scrape_url(url: str, max_chars: int = scraper.DEFAULT_MAX_CHARS) -> List[TextContent]:
        """Read any public web page and return its content as clean markdown."""
        return _text(scraper.scrape_url(url, max_chars=max_chars, jina_api_key=_jina_api_key()))

    @server.tool()
    def get_youtube_transcript(
        url: str,
        language: str = "en",
        max_chars: int = scraper.DEFAULT_MAX_CHARS,
    ) -> List[TextContent]:
        """Get the transcript of a public YouTube video from its subtitles or auto-captions."""
        return _text(scraper.get_youtube_transcript(url, language=language, max_chars=max_chars))

    return server


def main() -> None:
    server = create_server()
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    server.run(transport=transport)


if __name__ == "__main__":
    main()
