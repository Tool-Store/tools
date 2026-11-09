"""
The X reads offered to the AI, each in the user's own session (see x/page.py).

These are the four X actions Agent Reach offers: search, profile, tweets and thread.
Arguments must already be validated (handle, query, tweet id, limit).
"""

from typing import Any, Dict, List

from caller import Caller
from x import page

Rows = List[Dict[str, Any]]


async def search(caller: Caller, query: str, limit: int) -> Rows:
    return await page.read(caller, "search", {"query": query, "limit": limit}, f"results for '{query}'")


async def profile(caller: Caller, username: str) -> Rows:
    return await page.read(caller, "profile", {"username": username}, f"account '@{username}'")


async def tweets(caller: Caller, username: str, limit: int) -> Rows:
    return await page.read(caller, "tweets", {"username": username, "limit": limit}, f"account '@{username}'")


async def thread(caller: Caller, tweet_id: str, limit: int) -> Rows:
    return await page.read(caller, "thread", {"tweet_id": tweet_id, "limit": limit}, f"tweet {tweet_id}")
