"""
Runs Instagram reads in the user's own logged-in browser session.

Each read opens one Instagram page, then asks Instagram's own web API from inside it with
page_scripts/instagram_read.js, so the requests carry the user's cookies the way instagram.com's own
do. Instagram's answers become clear errors: not logged in, not found, or rate-limited. Ported from
OpenCLI's clis/instagram (Apache-2.0, see third_party/NOTICE).
"""

import logging
from typing import Any, Dict, List
from urllib.parse import urlsplit

import browser_session
from caller import Caller
from constants import INSTAGRAM, INSTAGRAM_LOGIN_WALL_PATHS
from errors import NotLoggedInError, PageReadError, RateLimitedError, login_needed_message

log = logging.getLogger(__name__)

RATE_LIMITED = (
    "Instagram is limiting requests for this account. Wait at least 30 minutes before the next Instagram call; "
    "retrying sooner makes the limit last longer."
)


async def read(caller: Caller, command: str, args: Dict[str, Any], start_url: str, target: str) -> List[Dict[str, Any]]:
    """Open `start_url` as the caller and run one read `command`; `target` names what was asked for, for errors."""
    async with browser_session.user_page(caller, INSTAGRAM) as page:
        await page.goto(start_url)
        _require_login(page.url)
        result = await page.run_script("instagram_read", {"command": command, "args": args})
    return _rows(result, command, target)


def _require_login(url: str) -> None:
    if any(urlsplit(url).path.startswith(path) for path in INSTAGRAM_LOGIN_WALL_PATHS):
        raise NotLoggedInError(_login_needed(f"Instagram sent the saved session to its security check or login page ({url})"))


def _rows(result: Any, command: str, target: str) -> List[Dict[str, Any]]:
    if not isinstance(result, dict):
        raise PageReadError(f"Instagram {command} returned an unreadable answer.")
    failure = result.get("failure")
    if isinstance(failure, dict):
        raise _failure_error(failure, command, target)
    rows = result.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise PageReadError(f"Instagram {command} returned an unreadable answer.")
    return rows


def _failure_error(failure: Dict[str, Any], command: str, target: str) -> Exception:
    code, message = failure.get("code"), str(failure.get("message") or "no details")
    log.warning("Instagram %s failed (%s): %s", command, code or "no code", message)
    if code == "AUTH_REQUIRED":
        return NotLoggedInError(_login_needed(f"Instagram did not accept the saved session ({message})"))
    if code == "RATE_LIMITED":
        return RateLimitedError(RATE_LIMITED)
    if code == "NOT_FOUND":
        return PageReadError(f"Instagram has no {target}. Check the name.")
    return PageReadError(f"Instagram {command} failed: {message}")


def _login_needed(reason: str) -> str:
    problem = f"{reason}; verify the account on Instagram if it asks, then log in again. Not logged in to"
    return login_needed_message(INSTAGRAM, problem)
