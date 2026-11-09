"""
Checks a running Social Media Agent server the way an AI client would.

By default no site is contacted and nothing counts toward the daily limit: the script checks
that the server answers, lists its 14 functions, and rejects bad input. With --live it also calls
each site once through the user's logged-in sessions and prints what each site returned.

Usage, from the tool folder with the container running:
    python scripts/smoke_test.py
    python scripts/smoke_test.py --live
"""

import argparse
import asyncio
import json
import sys
from datetime import timedelta
from typing import Any, Dict, List, Tuple

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_URL = "http://localhost:8000/mcp"
# The server allows a browser action up to 150s; the client must wait longer than that.
CALL_TIMEOUT = timedelta(seconds=180)
EXPECTED_TOOLS = {
    "start_login",
    "search_linkedin_jobs",
    "read_linkedin_job",
    "search_social",
    "get_social_profile",
    "get_linkedin_profile",
    "get_linkedin_company",
    "search_linkedin_posts",
    "get_instagram_profile",
    "get_instagram_posts",
    "search_x",
    "get_x_profile",
    "get_x_tweets",
    "get_x_thread",
}
INVALID_CALLS = [
    ("search_social", {"site": "linkedin", "query": "python"}, "Unsupported site"),
    ("search_linkedin_jobs", {"query": "python", "limit": 99}, "limit must be between"),
    ("get_x_profile", {"username": "https://x.com/a"}, "Invalid X username"),
    ("read_linkedin_job", {"url": "https://example.com/jobs/view/1"}, "Invalid LinkedIn job URL"),
    ("get_x_thread", {"tweet": "abc"}, "Invalid tweet"),
    ("get_linkedin_profile", {"profile_url": "https://example.com/in/a"}, "Invalid LinkedIn profile URL"),
    ("get_linkedin_profile", {"sections": ["hobbies"]}, "Unknown sections"),
    ("get_linkedin_company", {"company": "https://example.com/company/x"}, "Invalid LinkedIn company"),
    ("search_linkedin_posts", {"keywords": "AI", "pages": 9}, "pages must be between"),
    ("get_instagram_profile", {"username": "https://instagram.com/a"}, "Invalid username"),
    ("get_social_profile", {"site": "instagram", "username": "natgeo"}, "Unsupported site"),
]
LIVE_CALLS = [
    ("get_linkedin_profile", {}),
    ("get_linkedin_profile", {"profile_url": "https://www.linkedin.com/in/williamhgates/", "sections": ["experience"]}),
    ("get_linkedin_company", {"company": "microsoft"}),
    ("search_linkedin_posts", {"keywords": "AI marketing"}),
    ("get_social_profile", {"site": "facebook", "username": "nasa"}),
    ("get_instagram_profile", {"username": "natgeo"}),
    ("get_x_profile", {"username": "OpenAI"}),
]

Result = Tuple[str, bool, str]


async def _call(session: ClientSession, name: str, arguments: Dict[str, Any]) -> Tuple[bool, str]:
    result = await session.call_tool(name, arguments, read_timeout_seconds=CALL_TIMEOUT)
    return bool(result.isError), result.content[0].text if result.content else ""


async def _check_tools(session: ClientSession) -> List[Result]:
    names = {tool.name for tool in (await session.list_tools()).tools}
    return [(f"lists the {len(EXPECTED_TOOLS)} functions", names == EXPECTED_TOOLS, ", ".join(sorted(names)))]


async def _check_invalid_input(session: ClientSession) -> List[Result]:
    results = []
    for name, arguments, expected in INVALID_CALLS:
        is_error, text = await _call(session, name, arguments)
        results.append((f"rejects bad input: {name} {arguments}", is_error and expected in text, text[:120]))
    return results


async def _check_live(session: ClientSession) -> List[Result]:
    results = [await _check_linkedin(session)]
    for name, arguments in LIVE_CALLS:
        is_error, text = await _call(session, name, arguments)
        results.append(_live_result(f"{name} {arguments}", is_error, text))
    return results


async def _check_linkedin(session: ClientSession) -> Result:
    is_error, text = await _call(session, "search_linkedin_jobs", {"query": "python", "limit": 1})
    if is_error or not json.loads(text)["items"]:
        return _live_result("search_linkedin_jobs", is_error, text)
    job_url = json.loads(text)["items"][0]["url"]
    is_error, text = await _call(session, "read_linkedin_job", {"url": job_url})
    return _live_result("search_linkedin_jobs + read_linkedin_job", is_error, text)


def _live_result(label: str, is_error: bool, text: str) -> Result:
    """A site error (not logged in, rate limited) is a valid answer; only an unreadable answer fails."""
    if is_error:
        return (f"live {label}", True, f"site answered with an error: {text[:160]}")
    try:
        response = json.loads(text)
    except json.JSONDecodeError:
        return (f"live {label}", False, f"answer is not JSON: {text[:160]}")
    return (f"live {label}", True, f"{response['count']} item(s), {response['requests_left_today']} requests left today")


async def _run_checks(url: str, live: bool) -> List[Result]:
    async with (
        streamable_http_client(url) as (read_stream, write_stream, _),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        results = await _check_tools(session) + await _check_invalid_input(session)
        if live:
            results += await _check_live(session)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--url", default=DEFAULT_URL, help=f"MCP endpoint (default {DEFAULT_URL})")
    parser.add_argument("--live", action="store_true", help="also call each site once (counts toward daily limits)")
    args = parser.parse_args()

    results = asyncio.run(_run_checks(args.url, args.live))
    for label, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}  {label}\n      {detail}")
    failed = sum(not passed for _, passed, _ in results)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
