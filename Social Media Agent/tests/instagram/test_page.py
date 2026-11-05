import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import pytest_asyncio

import browser_session
import login_store
from caller import Caller
from errors import NotLoggedInError, PageReadError, RateLimitedError
from instagram import page as instagram_page

USER = Caller("user-1")
NASA = {
    "username": "nasa",
    "full_name": "NASA",
    "is_verified": True,
    "is_private": False,
    "biography": "Exploring the universe",
    "follower_count": 98,
    "following_count": 80,
    "media_count": 4000,
    "is_business": True,
    "category": "Government organization",
    "external_url": "https://nasa.gov",
    "hd_profile_pic_url_info": {"url": "https://cdn/pic.jpg"},
}
POST = {
    "code": "Cabc",
    "user": {"username": "nasa"},
    "caption": {"text": "Full caption\nwith two lines"},
    "like_count": 120,
    "comment_count": 4,
    "media_type": 1,
    "taken_at": 1762300800,
}
REEL = {"code": "Cdef", "user": {"username": "natgeo"}, "play_count": 900, "media_type": 2}
SUMMARY = '<meta property="og:description" content="98 Followers, 80 Following, 4,000 Posts - See Instagram photos">'
TIMELINE = "xdt_api__v1__feed__user_timeline_graphql_connection"


def _loader_block(data):
    """Wraps data the way Instagram's page loader does (as seen live on 2026-11-05), several levels deep."""
    result = {"__bbox": {"complete": True, "result": {"data": data}}}
    stream = [["RelayPrefetchedStreamCache", "next", [], ["adp_1", result]]]
    block = {"require": [["ScheduledServerJS", "handle", None, [{"__bbox": {"require": stream}}]]]}
    return f'<script type="application/json">{json.dumps(block)}</script>'


def _page(html_class, head="", body=""):
    return f'<!DOCTYPE html><html class="{html_class}"><head>{head}</head><body>{body}</body></html>'.encode()


PAGES = {
    "/nasa/": _page(
        "logged-in",
        SUMMARY,
        _loader_block({"user": NASA})
        + _loader_block({TIMELINE: {"edges": [{"node": POST}, {"node": REEL}]}})
        + '<script type="application/json">not json</script>',
    ),
    "/summary/": _page("logged-in", SUMMARY),
    "/nobody/": _page("logged-in", "", "Sorry, this page isn't available."),
    "/busy/": _page("logged-in", "", "Please wait a few minutes before you try again."),
}


class _FakeInstagram(BaseHTTPRequestHandler):
    """Serves profile pages like Instagram does; without the saved session cookie every page is the logged-out one."""

    def do_GET(self):
        logged_in = "sessionid=abc" in (self.headers.get("Cookie") or "")
        page = PAGES.get(self.path, _page("logged-in")) if logged_in else _page("no-js not-logged-in")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def instagram_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeInstagram)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


@pytest.fixture
def logged_in(local_store):
    login_store.save_cookies(USER, "instagram", [{"name": "sessionid", "value": "abc", "domain": "127.0.0.1", "path": "/"}])


@pytest_asyncio.fixture
async def browser():
    yield
    await browser_session.shutdown()


async def _read(instagram_url, command, args, path, target="account 'nasa'"):
    return await instagram_page.read(USER, command, args, instagram_url + path, target)


@pytest.mark.asyncio
async def test_profile_is_read_from_the_data_the_page_already_carries(logged_in, browser, instagram_url):
    [profile] = await _read(instagram_url, "profile", {"username": "NASA"}, "nasa/")

    assert profile == {
        "username": "nasa",
        "name": "NASA",
        "verified": True,
        "private": False,
        "url": "https://www.instagram.com/nasa/",
        "bio": "Exploring the universe",
        "followers": 98,
        "following": 80,
        "posts": 4000,
        "business": True,
        "category": "Government organization",
        "website": "https://nasa.gov",
        "avatar_url": "https://cdn/pic.jpg",
    }


@pytest.mark.asyncio
async def test_profile_falls_back_to_the_page_summary_counts(logged_in, browser, instagram_url):
    [profile] = await _read(instagram_url, "profile", {"username": "nasa"}, "summary/")

    assert (profile["followers"], profile["following"], profile["posts"]) == ("98", "80", "4,000")
    assert "only these counts" in profile["note"]


@pytest.mark.asyncio
async def test_posts_keep_full_captions_and_links(logged_in, browser, instagram_url):
    posts = await _read(instagram_url, "posts", {"username": "nasa", "limit": 2}, "nasa/")

    assert posts == [
        {"user": "nasa", "caption": "Full caption\nwith two lines", "likes": 120, "comments": 4, "type": "photo",
         "posted_at": "2025-11-05T00:00:00.000Z", "url": "https://www.instagram.com/p/Cabc/"},
        {"user": "natgeo", "caption": "", "likes": 900, "comments": 0, "type": "video", "posted_at": "",
         "url": "https://www.instagram.com/p/Cdef/"},
    ]


@pytest.mark.asyncio
async def test_posts_are_cut_to_the_limit(logged_in, browser, instagram_url):
    posts = await _read(instagram_url, "posts", {"username": "nasa", "limit": 1}, "nasa/")

    assert [post["url"] for post in posts] == ["https://www.instagram.com/p/Cabc/"]


@pytest.mark.asyncio
async def test_page_without_posts_data_is_an_error(logged_in, browser, instagram_url):
    with pytest.raises(PageReadError, match="carried no posts data"):
        await _read(instagram_url, "posts", {"username": "nasa", "limit": 5}, "summary/")


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["profile", "posts"])
async def test_unknown_account_is_reported_as_not_found(logged_in, browser, instagram_url, command):
    with pytest.raises(PageReadError, match="Instagram has no account 'nobody'"):
        await _read(instagram_url, command, {"username": "nobody", "limit": 5}, "nobody/", "account 'nobody'")


@pytest.mark.asyncio
async def test_logged_out_page_asks_the_user_to_log_in(local_store, browser, instagram_url):
    login_store.save_cookies(USER, "instagram", [{"name": "sessionid", "value": "expired", "domain": "127.0.0.1", "path": "/"}])

    with pytest.raises(NotLoggedInError, match="Instagram did not accept the saved session"):
        await _read(instagram_url, "profile", {"username": "nasa"}, "nasa/")


@pytest.mark.asyncio
async def test_wait_page_stops_with_a_wait_message(logged_in, browser, instagram_url):
    with pytest.raises(RateLimitedError, match="Wait at least"):
        await _read(instagram_url, "posts", {"username": "nasa", "limit": 1}, "busy/")


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["accounts/login/?next=/nasa/", "challenge/abc/", "accounts/suspended/"])
async def test_login_wall_page_asks_the_user_to_log_in(logged_in, browser, instagram_url, path):
    with pytest.raises(NotLoggedInError, match="security check or login page"):
        await _read(instagram_url, "profile", {"username": "nasa"}, path)
