import asyncio
import json

import server


def test_server_registers_all_tools():
    tools = asyncio.run(server.create_server().list_tools())

    assert sorted(tool.name for tool in tools) == [
        "get_social_posts",
        "get_social_profile",
        "get_telegram_channel_posts",
        "get_youtube_transcript",
        "scrape_url",
    ]


def test_tool_output_is_valid_json():
    payload = {"url": "https://example.com", "content": "héllo", "truncated": False}

    [block] = server._text(payload)

    assert json.loads(block.text) == payload
