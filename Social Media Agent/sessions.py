"""
Login and daily usage for the user's sites.

start_login opens a site's login page in the Agent Reach browser; start_browser_login does the same
for sites on our own browser sessions and saves the user's login once they finish. Both say where
the user can see the browser. The daily limit counts requests per user and site, so automated use
stays low enough to protect each user's accounts. Counts are a user record in user_store, so restarts
keep them. The lock keeps counts exact within one server process; several Toolstore replicas could each
let one extra request through at the same moment.
"""

import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import agent_reach
import browser_session
import login_store
import user_store
import validators
from caller import Caller
from constants import (
    BROWSER_LOGIN_PAGES,
    DAILY_REQUEST_LIMIT_ENV,
    DEFAULT_DAILY_REQUEST_LIMIT,
    DEFAULT_INSTAGRAM_DAILY_REQUEST_LIMIT,
    DEFAULT_VIEWER_URL,
    INSTAGRAM,
    INSTAGRAM_DAILY_REQUEST_LIMIT_ENV,
    LOGIN_POLL_SECONDS,
    LOGIN_WINDOW_SECONDS,
    VIEWER_URL_ENV,
)
from errors import DailyLimitError, LoginBusyError

log = logging.getLogger(__name__)

USAGE_RECORD = "usage"
# Sites with their own daily limit setting: (setting name, default)
SITE_DAILY_LIMITS = {INSTAGRAM: (INSTAGRAM_DAILY_REQUEST_LIMIT_ENV, DEFAULT_INSTAGRAM_DAILY_REQUEST_LIMIT)}

# Tool calls run in parallel worker threads; counting must not lose updates.
_usage_lock = threading.Lock()
# The viewer shows one screen, so only one login window may be open at a time.
_login_task: Optional[asyncio.Task] = None


def start_login(site: str) -> Dict[str, str]:
    agent_reach.open_login(site)
    return _viewer_reply(site, "then retry.")


async def start_browser_login(caller: Caller, site: str) -> Dict[str, str]:
    """Open the site's login page in the viewer; the login is saved for the user once they finish."""
    global _login_task
    if _login_task is not None and not _login_task.done():
        raise LoginBusyError(
            f"Another login is open in the browser viewer. Retry within {LOGIN_WINDOW_SECONDS // 60} minutes."
        )
    _login_task = asyncio.create_task(_save_login_when_finished(caller, site))
    return _viewer_reply(
        site,
        f"the login is saved automatically as soon as it finishes (the window stays open for "
        f"{LOGIN_WINDOW_SECONDS // 60} minutes), then retry.",
    )


async def _save_login_when_finished(caller: Caller, site: str) -> None:
    login_url, login_cookie = BROWSER_LOGIN_PAGES[site]
    try:
        cookies = await browser_session.wait_for_login(login_url, login_cookie, LOGIN_WINDOW_SECONDS, LOGIN_POLL_SECONDS)
        await asyncio.to_thread(login_store.save_cookies, caller, site, cookies)
        log.info("Saved the %s login", site)
    except Exception:
        # Runs in the background with no caller to raise to; the next request reports "not logged in".
        log.exception("The %s login did not finish", site)


def _viewer_reply(site: str, after_login: str) -> Dict[str, str]:
    viewer_url = os.getenv(VIEWER_URL_ENV, DEFAULT_VIEWER_URL)
    return {
        "site": site,
        "viewer_url": viewer_url,
        "next": f"Ask the user to open {viewer_url}, log in to {site} there with their own account, {after_login}",
    }


def count_request(caller: Caller, site: str, page_loads: int = 1) -> int:
    """Count a call's page loads for the user and site and return how many are left today.

    Raises when they do not all fit in what is left, and then counts nothing. Called before the site is
    contacted, so a call that then fails still counts: the site saw it.
    """
    limit = validators.positive_int_setting(*SITE_DAILY_LIMITS.get(site, (DAILY_REQUEST_LIMIT_ENV, DEFAULT_DAILY_REQUEST_LIMIT)))
    with _usage_lock:
        usage = _load_usage(caller)
        used = usage["counts"].get(site, 0)
        if used >= limit:
            raise DailyLimitError(
                f"Daily limit of {limit} requests for {site} reached. It resets at 00:00 UTC."
            )
        if used + page_loads > limit:
            raise DailyLimitError(
                f"This call needs {page_loads} page loads but only {limit - used} of {limit} are left "
                f"for {site} today. Ask for fewer sections or pages; the limit resets at 00:00 UTC."
            )
        usage["counts"][site] = used + page_loads
        user_store.save(caller, USAGE_RECORD, usage)
    return limit - used - page_loads


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _load_usage(caller: Caller) -> Dict[str, Any]:
    fresh = {"date": _today(), "counts": {}}
    try:
        usage = user_store.load(caller, USAGE_RECORD)
    except json.JSONDecodeError as exc:
        # A damaged counter must not lock the user out for good; start the day's count again.
        log.warning("Usage record is unreadable (%s); starting a new count", exc)
        return fresh
    if not isinstance(usage, dict) or usage.get("date") != fresh["date"] or not isinstance(usage.get("counts"), dict):
        return fresh
    return usage
