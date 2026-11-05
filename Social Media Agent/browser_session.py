"""
Opens a short-lived browser session for one request, logged in as the calling user.

One headless Chromium is shared by all users. Each request gets its own browser context (separate
cookies and storage), loaded with that user's saved login and closed when the request ends, so users
never see each other's sessions. Sites rotate their cookies, so the cookies a successful request
ends with are saved back. Page scripts live in page_scripts/ (sources in third_party/NOTICE).
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Pattern

# Patchright is Playwright with the signs of automation removed, so sites flag the browser less often.
from patchright.async_api import Browser, Page, Playwright, async_playwright

# Raised by page actions when the browser fails (timeout, closed page); site readers catch it per section.
from patchright.async_api import Error as BrowserError
from patchright.async_api import TimeoutError as PlaywrightTimeoutError

import login_store
import validators
from caller import Caller
from constants import (
    BROWSER_CHANNEL,
    BROWSER_LOCALE,
    DEFAULT_MAX_BROWSER_SESSIONS,
    DOM_QUIET_MS,
    MAX_BROWSER_SESSIONS_ENV,
    NAVIGATED_AWAY,
    NAVIGATION_TIMEOUT_MS,
    PAGE_SCRIPT_ATTEMPTS,
    PAGE_SETTLE_MS,
)
from errors import LoginTimeoutError

log = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).parent / "page_scripts"

_playwright: Optional[Playwright] = None
_browser: Optional[Browser] = None
_user_agent: Optional[str] = None
# Created on first use so they belong to the server's running event loop.
_launch_lock: Optional[asyncio.Lock] = None
_slots: Optional[asyncio.Semaphore] = None


class SitePage:
    """The page actions the site readers use: open, wait, scroll, click and run page scripts."""

    def __init__(self, page: Page) -> None:
        self._page = page

    @property
    def url(self) -> str:
        """Where the page is now, after any redirect."""
        return self._page.url

    async def goto(self, url: str) -> None:
        await self._page.goto(url, wait_until="load", timeout=NAVIGATION_TIMEOUT_MS)
        await self._wait_until_quiet(PAGE_SETTLE_MS)

    async def wait(self, seconds: float) -> None:
        """Wait until the page stops changing, but no longer than `seconds`."""
        await self._wait_until_quiet(int(seconds * 1000))

    async def auto_scroll(self, times: int, delay_ms: int) -> None:
        await self._evaluate(load_script("auto_scroll"), [times, delay_ms])

    async def evaluate(self, expression: str) -> Any:
        return await self._evaluate(expression)

    async def run_script(self, name: str, argument: Any = None) -> Any:
        return await self._evaluate(load_script(name), argument)

    async def wait_until(self, condition: str, timeout_ms: int) -> bool:
        """Wait for a page condition (a JS function); False when it is still not true after `timeout_ms`."""
        try:
            await self._page.wait_for_function(condition, timeout=timeout_ms)
        except PlaywrightTimeoutError:
            return False
        return True

    async def click_first(self, selector: str, text_pattern: Optional[Pattern[str]] = None, timeout_ms: int = 2_000) -> bool:
        """Click the first visible element matching `selector` and `text_pattern`; False when there is none."""
        matches = self._page.locator(selector)
        if text_pattern is not None:
            matches = matches.filter(has_text=text_pattern)
        target = matches.first
        try:
            if not await target.is_visible():
                return False
            await target.scroll_into_view_if_needed(timeout=timeout_ms)
            await target.click(timeout=timeout_ms)
        except PlaywrightTimeoutError:
            return False
        return True

    async def _wait_until_quiet(self, max_ms: int) -> None:
        await self._evaluate(load_script("dom_stable"), [max_ms, min(DOM_QUIET_MS, max_ms)])

    async def _evaluate(self, script: str, argument: Any = None) -> Any:
        """Run a page script; when the page moves on while it runs (a redirect), run it again on the new page."""
        for attempt in range(1, PAGE_SCRIPT_ATTEMPTS + 1):
            try:
                if argument is None:
                    return await self._page.evaluate(script)
                return await self._page.evaluate(script, argument)
            except BrowserError as error:
                if NAVIGATED_AWAY not in str(error) or attempt == PAGE_SCRIPT_ATTEMPTS:
                    raise
                log.info("The page moved on to %s while a script ran; running it there", self._page.url)
                await self._page.wait_for_load_state("load", timeout=NAVIGATION_TIMEOUT_MS)


@lru_cache(maxsize=None)
def load_script(name: str) -> str:
    return (SCRIPTS_DIR / f"{name}.js").read_text(encoding="utf-8")


@asynccontextmanager
async def user_page(caller: Caller, site: str) -> AsyncIterator[SitePage]:
    """Yield a page logged in as the caller; raises NotLoggedInError when they have no saved login."""
    # The login may come from Toolstore over HTTP, so it is loaded and saved off the event loop.
    cookies = await asyncio.to_thread(login_store.load_cookies, caller, site)
    async with _session_slots():
        browser = await _shared_browser()
        context = await browser.new_context(locale=BROWSER_LOCALE, user_agent=_user_agent)
        try:
            await context.add_cookies(cookies)
            yield SitePage(await context.new_page())
            await asyncio.to_thread(login_store.save_cookies, caller, site, await context.cookies())
        finally:
            await context.close()


async def wait_for_login(login_url: str, login_cookie: str, timeout_seconds: int, poll_seconds: float) -> List[Dict[str, Any]]:
    """Show the login page in a visible browser and return its cookies once `login_cookie` is set."""
    browser = await (await _shared_playwright()).chromium.launch(headless=False, channel=BROWSER_CHANNEL)
    try:
        context = await browser.new_context(locale=BROWSER_LOCALE)
        await (await context.new_page()).goto(login_url, timeout=NAVIGATION_TIMEOUT_MS)
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            cookies = await context.cookies()
            if any(cookie["name"] == login_cookie for cookie in cookies):
                return cookies
            await asyncio.sleep(poll_seconds)
        raise LoginTimeoutError(f"Login was not finished within {timeout_seconds // 60} minutes.")
    finally:
        await browser.close()


async def shutdown() -> None:
    """Close the shared browser; the next request starts a new one."""
    global _browser, _playwright, _launch_lock, _slots, _user_agent
    if _browser is not None:
        await _browser.close()
    if _playwright is not None:
        await _playwright.stop()
    _browser = _playwright = _launch_lock = _slots = _user_agent = None


async def _shared_playwright() -> Playwright:
    global _playwright, _launch_lock
    _launch_lock = _launch_lock or asyncio.Lock()
    async with _launch_lock:
        if _playwright is None:
            _playwright = await async_playwright().start()
    return _playwright


async def _shared_browser() -> Browser:
    global _browser, _user_agent
    playwright = await _shared_playwright()
    async with _launch_lock:
        if _browser is None or not _browser.is_connected():
            _browser = await playwright.chromium.launch(headless=True, channel=BROWSER_CHANNEL)
            _user_agent = await _visible_user_agent(_browser)
            log.info("Started the shared headless browser")
    return _browser


async def _visible_user_agent(browser: Browser) -> str:
    """The browser's own name with "HeadlessChrome" as "Chrome", exactly as the visible login window reports it.

    A session logged in through the visible window would otherwise come back from a "HeadlessChrome", which
    sites treat as a bot. The full-browser headless mode (BROWSER_CHANNEL) already reports normal client hints.
    """
    context = await browser.new_context()
    try:
        agent = await (await context.new_page()).evaluate("navigator.userAgent")
    finally:
        await context.close()
    return str(agent).replace("HeadlessChrome/", "Chrome/")


def _session_slots() -> asyncio.Semaphore:
    global _slots
    if _slots is None:
        _slots = asyncio.Semaphore(validators.positive_int_setting(MAX_BROWSER_SESSIONS_ENV, DEFAULT_MAX_BROWSER_SESSIONS))
    return _slots
