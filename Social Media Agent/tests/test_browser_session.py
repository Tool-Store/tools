import asyncio
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import pytest_asyncio

import browser_session
import login_store
from caller import Caller
from errors import NotLoggedInError

PAGE = b"""<html><body><p id="cookies"></p><div id="feed" style="height:3000px"></div>
<main><ul id="entries"><li>First entry</li></ul>
<button id="more" onclick="this.previousElementSibling.insertAdjacentHTML('beforeend', '<li>Extra entry</li>')">Show more</button>
<button style="display:none">Show all</button></main>
<script>
setTimeout(() => document.body.insertAdjacentHTML('beforeend', '<p id="late">late</p>'), 300);
document.getElementById('cookies').textContent = document.cookie;
document.cookie = 'rotated=fresh; path=/';
window.addEventListener('scroll', () => {
  const more = document.createElement('div');
  more.style.height = '2000px';
  more.className = 'loaded';
  document.getElementById('feed').appendChild(more);
}, { once: true });
</script></body></html>"""


# Like LinkedIn sending a session to its security check: the page moves on by itself after it has loaded.
REDIRECTING_PAGE = b"""<html><body><main>Loading</main>
<script>setTimeout(() => { location.href = '/checkpoint/challenge'; }, 150);</script></body></html>"""


class _PageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if self.path == "/whoami":
            # Echoes what the browser tells sites about itself.
            self.wfile.write(json.dumps({"ua": self.headers.get("User-Agent"), "hints": self.headers.get("Sec-CH-UA")}).encode())
            return
        self.wfile.write(REDIRECTING_PAGE if self.path == "/redirects" else PAGE)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PageHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


@pytest_asyncio.fixture
async def browser():
    yield
    await browser_session.shutdown()


def _login(user_id, value):
    login_store.save_cookies(Caller(user_id), "site", [{"name": "session", "value": value, "domain": "127.0.0.1", "path": "/"}])


@pytest.mark.asyncio
async def test_page_opens_with_the_users_saved_login(local_store, browser, site_url):
    _login("user-1", "user-1-session")

    async with browser_session.user_page(Caller("user-1"), "site") as page:
        await page.goto(site_url)
        shown = await page.evaluate("document.getElementById('cookies').textContent")

    assert "session=user-1-session" in shown


@pytest.mark.asyncio
async def test_parallel_users_never_see_each_others_login(local_store, browser, site_url):
    _login("user-1", "user-1-session")
    _login("user-2", "user-2-session")

    async def read_cookies(user_id):
        async with browser_session.user_page(Caller(user_id), "site") as page:
            await page.goto(site_url)
            return await page.evaluate("document.getElementById('cookies').textContent")

    first, second = await asyncio.gather(read_cookies("user-1"), read_cookies("user-2"))

    assert "user-1-session" in first and "user-2-session" not in first
    assert "user-2-session" in second and "user-1-session" not in second


@pytest.mark.asyncio
async def test_cookies_the_site_rotates_are_saved_after_a_successful_request(local_store, browser, site_url):
    _login("user-1", "user-1-session")

    async with browser_session.user_page(Caller("user-1"), "site") as page:
        await page.goto(site_url)

    saved = {cookie["name"]: cookie["value"] for cookie in login_store.load_cookies(Caller("user-1"), "site")}
    assert saved == {"session": "user-1-session", "rotated": "fresh"}


@pytest.mark.asyncio
async def test_cookies_are_not_saved_when_the_request_fails(local_store, browser, site_url):
    _login("user-1", "user-1-session")

    with pytest.raises(RuntimeError, match="extraction failed"):
        async with browser_session.user_page(Caller("user-1"), "site") as page:
            await page.goto(site_url)
            raise RuntimeError("extraction failed")

    assert [cookie["name"] for cookie in login_store.load_cookies(Caller("user-1"), "site")] == ["session"]


@pytest.mark.asyncio
async def test_user_without_a_saved_login_is_asked_to_log_in(local_store, browser):
    with pytest.raises(NotLoggedInError, match="start_login"):
        async with browser_session.user_page(Caller("nobody"), "site"):
            pass


@pytest.mark.asyncio
async def test_wait_auto_scroll_and_scripts_run_in_the_page(local_store, browser, site_url):
    _login("user-1", "user-1-session")

    async with browser_session.user_page(Caller("user-1"), "site") as page:
        await page.goto(site_url)
        await page.auto_scroll(times=2, delay_ms=300)
        await page.wait(1)
        loaded = await page.evaluate("document.querySelectorAll('.loaded').length")
        logged_out = await page.run_script("linkedin_auth_probe")

    assert loaded == 1
    assert logged_out is False


@pytest.mark.asyncio
async def test_browser_restarts_after_shutdown(local_store, browser, site_url):
    _login("user-1", "user-1-session")
    async with browser_session.user_page(Caller("user-1"), "site") as page:
        await page.goto(site_url)
    await browser_session.shutdown()

    async with browser_session.user_page(Caller("user-1"), "site") as page:
        await page.goto(site_url)
        assert await page.evaluate("1 + 1") == 2


@pytest.mark.asyncio
async def test_url_is_where_the_page_ended_up(local_store, browser, site_url):
    _login("user-1", "user-1-session")
    async with browser_session.user_page(Caller("user-1"), "site") as page:
        await page.goto(site_url + "?from=test")
        assert page.url == site_url + "?from=test"


@pytest.mark.asyncio
async def test_wait_until_reports_whether_the_condition_came_true(local_store, browser, site_url):
    _login("user-1", "user-1-session")
    async with browser_session.user_page(Caller("user-1"), "site") as page:
        await page.goto(site_url)
        assert await page.wait_until("() => document.getElementById('late') !== null", timeout_ms=3_000) is True
        assert await page.wait_until("() => document.getElementById('never') !== null", timeout_ms=200) is False


@pytest.mark.asyncio
async def test_click_first_clicks_only_a_visible_matching_element(local_store, browser, site_url):
    _login("user-1", "user-1-session")
    async with browser_session.user_page(Caller("user-1"), "site") as page:
        await page.goto(site_url)
        assert await page.click_first("main button", re.compile(r"^Show more$")) is True
        assert await page.click_first("main button", re.compile(r"^Show all$")) is False
        assert await page.click_first("main button", re.compile(r"^Nothing$")) is False
        entries = await page.evaluate("document.querySelectorAll('#entries li').length")

    assert entries == 2


@pytest.mark.asyncio
async def test_section_content_script_returns_main_text_and_links(local_store, browser, site_url):
    _login("user-1", "user-1-session")
    async with browser_session.user_page(Caller("user-1"), "site") as page:
        await page.goto(site_url)
        content = await page.run_script("linkedin_section_content", {"selectors": ["main"]})

    assert content["source"] == "root"
    assert "First entry" in content["text"] and "Show more" in content["text"]
    assert content["references"] == []


@pytest.mark.asyncio
async def test_page_that_redirects_while_it_is_read_is_read_where_it_landed(local_store, browser, site_url):
    _login("user-1", "user-1-session")

    async with browser_session.user_page(Caller("user-1"), "site") as page:
        await page.goto(site_url + "redirects")
        await page.wait(1)
        entries = await page.evaluate("document.querySelectorAll('#entries li').length")

    assert page.url == site_url + "checkpoint/challenge"
    assert entries == 1


@pytest.mark.asyncio
async def test_reading_browser_does_not_tell_sites_it_is_headless(local_store, browser, site_url):
    # A session logged in through the visible window must not suddenly come from a "HeadlessChrome".
    _login("user-1", "user-1-session")

    async with browser_session.user_page(Caller("user-1"), "site") as page:
        await page.goto(site_url)
        told = await page.evaluate("fetch('/whoami').then((r) => r.json())")
        brands = await page.evaluate("(navigator.userAgentData?.brands || []).map((b) => b.brand).join(',')")

    assert "Headless" not in told["ua"] and "Chrome/" in told["ua"]
    assert "Headless" not in (told["hints"] or "")
    assert "Headless" not in brands
