"""
Runs X reads in the user's own logged-in browser session.

Each read opens x.com's home page as the user, then asks X's own web API from inside it with
page_scripts/x_read.js, so the requests carry the user's cookies the way x.com's own do. X's answers
become clear errors: not logged in, not found, or rate-limited. Ported from OpenCLI 1.8.7 clis/twitter
(Apache-2.0, see third_party/NOTICE).
"""

import logging
from typing import Any, Dict, List
from urllib.parse import urlsplit

import browser_session
from caller import Caller
from constants import X_HOME_URL, X_LOGIN_WALL_PATHS, X
from errors import NotLoggedInError, PageReadError, RateLimitedError, login_needed_message

log = logging.getLogger(__name__)

RATE_LIMITED = (
    "X is limiting requests for this account. Wait at least 15 minutes before the next X call; "
    "retrying sooner makes the limit last longer."
)


async def read(caller: Caller, command: str, args: Dict[str, Any], target: str) -> List[Dict[str, Any]]:
    """Run one read `command` on x.com as the caller; `target` names what was asked for, for errors."""
    async with browser_session.user_page(caller, X) as page:
        await page.goto(X_HOME_URL)
        _require_login(page.url)
        result = await page.run_script("x_read", {"command": command, "args": args})
    return _rows(result, command, target)


def _require_login(url: str) -> None:
    if any(urlsplit(url).path.startswith(path) for path in X_LOGIN_WALL_PATHS):
        raise NotLoggedInError(_login_needed(f"X sent the saved session to its login or account check page ({url})"))


def _rows(result: Any, command: str, target: str) -> List[Dict[str, Any]]:
    if not isinstance(result, dict):
        raise PageReadError(f"X {command} returned an unreadable answer.")
    failure = result.get("failure")
    if isinstance(failure, dict):
        raise _failure_error(failure, command, target)
    rows = result.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise PageReadError(f"X {command} returned an unreadable answer.")
    return rows


def _failure_error(failure: Dict[str, Any], command: str, target: str) -> Exception:
    code, message = failure.get("code"), str(failure.get("message") or "no details")
    log.warning("X %s failed (%s): %s", command, code or "no code", message)
    if code == "AUTH_REQUIRED":
        return NotLoggedInError(_login_needed(f"X did not accept the saved session ({message})"))
    if code == "RATE_LIMITED":
        return RateLimitedError(RATE_LIMITED)
    if code == "NOT_FOUND":
        return PageReadError(f"X has no {target}. Check the name or link.")
    return PageReadError(f"X {command} failed: {message}")


def _login_needed(reason: str) -> str:
    problem = f"{reason}; verify the account on x.com if it asks, then log in again. Not logged in to"
    return login_needed_message(X, problem)
