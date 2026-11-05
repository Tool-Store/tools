"""
The Instagram reads offered to the AI, each in the user's own session (see instagram/page.py).

Both open the account's own page, as a person would, and read the data that page already carries.
Arguments must already be validated (username, limit).
"""

from typing import Any, Dict, List
from urllib.parse import quote

from caller import Caller
from constants import INSTAGRAM_ORIGIN
from instagram import page

Rows = List[Dict[str, Any]]


async def profile(caller: Caller, username: str) -> Rows:
    return await page.read(caller, "profile", {"username": username}, _account_page(username), f"account '{username}'")


async def posts(caller: Caller, username: str, limit: int) -> Rows:
    args = {"username": username, "limit": limit}
    return await page.read(caller, "posts", args, _account_page(username), f"account '{username}'")


def _account_page(username: str) -> str:
    return f"{INSTAGRAM_ORIGIN}/{quote(username, safe='')}/"
