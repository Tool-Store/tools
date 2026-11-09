import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
import pytest_asyncio

import browser_session
import login_store
from caller import Caller
from errors import NotLoggedInError, PageReadError, RateLimitedError
from x import page as x_page

USER = Caller("user-1")
CSRF = "csrf-123"
CREATED_AT = "Mon Nov 09 05:20:13 +0000 2026"
# X's renamed query id, as its own website script carries it (seen in OpenCLI's bundle parser).
BUNDLE = 'window.bundle = \'queryId:"FreshId",operationName:"UserByScreenName",operationType:"query"\';'
NASA = {
    "rest_id": "11348282",
    "is_blue_verified": True,
    "core": {"screen_name": "NASA", "name": "NASA", "created_at": "Wed Dec 19 20:20:32 +0000 2007"},
    "legacy": {
        "description": "Explore the universe",
        "followers_count": 92,
        "friends_count": 180,
        "statuses_count": 73000,
        "favourites_count": 16000,
        "entities": {"url": {"urls": [{"expanded_url": "https://nasa.gov"}]}},
    },
    "location": {"location": "Pale Blue Dot"},
}


def _tweet(tweet_id, text, author="NASA", **legacy):
    return {
        "__typename": "Tweet",
        "rest_id": tweet_id,
        "core": {"user_results": {"result": {"core": {"screen_name": author, "name": f"{author} name"}}}},
        "legacy": {"full_text": text, "created_at": CREATED_AT, "favorite_count": 5, "retweet_count": 2,
                   "reply_count": 1, **legacy},
        "views": {"count": "900"},
    }


def _entry(tweet):
    return {"entryId": f"tweet-{tweet['rest_id']}",
            "content": {"entryType": "TimelineTimelineItem", "itemContent": {"tweet_results": {"result": tweet}}}}


def _cursor(value):
    return {"entryId": "cursor-bottom-1", "content": {"entryType": "TimelineTimelineCursor", "cursorType": "Bottom", "value": value}}


def _timeline(*entries):
    return {"instructions": [{"type": "TimelineAddEntries", "entries": list(entries)}]}


VIDEO = {"extended_entities": {"media": [{"type": "video", "media_url_https": "https://pbs/poster.jpg", "video_info": {
    "variants": [{"content_type": "video/mp4", "bitrate": 256, "url": "https://video/low.mp4"},
                 {"content_type": "application/x-mpegURL", "url": "https://video/list.m3u8"},
                 {"content_type": "video/mp4", "bitrate": 2176, "url": "https://video/high.mp4"}]}}]}}
PHOTO = {"extended_entities": {"media": [{"type": "photo", "media_url_https": "https://pbs/photo.jpg"}]}}
FIRST = _tweet("101", "First tweet", **VIDEO)
SECOND = {**_tweet("102", "RT @SpaceX: launch", is_quote_status=True),
          "quoted_status_result": {"result": {"rest_id": "555"}}}
THIRD = _tweet("103", "Third tweet", **PHOTO)
PINNED = _tweet("100", "Pinned tweet")
REPLY = _tweet("21", "@NASA great", author="fan", in_reply_to_status_id_str="20")
USER_TWEETS = {
    None: {"instructions": [
        {"type": "TimelinePinEntry", "entry": _entry(PINNED)},
        *_timeline(_entry(FIRST), _entry(SECOND), _cursor("page-2"))["instructions"],
    ]},
    "page-2": _timeline(_entry(THIRD), _cursor("page-2")),
}
SEARCH = {None: _timeline(_entry(FIRST), _cursor("page-2")), "page-2": _timeline(_entry(THIRD))}
THREAD = {"instructions": [{"type": "TimelineAddEntries", "entries": [
    _entry(_tweet("20", "Main tweet")),
    {"entryId": "conversationthread-21", "content": {"entryType": "TimelineTimelineModule", "items": [
        {"item": {"itemContent": {"tweet_results": {"result": REPLY}}}}]}},
]}]}


class _FakeX(BaseHTTPRequestHandler):
    """Serves x.com's pages and the web API answers its reads use; without the session cookie, /home goes to login."""

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path.startswith("/i/api/graphql/"):
            self._graphql(url.path, {name: json.loads(values[0]) for name, values in parse_qs(url.query).items()})
        elif url.path == "/home":
            self._home()
        elif url.path == "/responsive-web/client-web/main.js":
            self._send(200, BUNDLE, "text/javascript")
        else:
            self._send(200, "<html><body>page</body></html>", "text/html")

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self._graphql(urlsplit(self.path).path, payload)

    def _home(self):
        session = self._cookie("auth_token")
        redirects = {None: "/i/flow/login?redirect_after_login=%2Fhome", "locked": "/account/access"}
        if session in redirects:
            self.send_response(302)
            self.send_header("Location", redirects[session])
            self.end_headers()
            return
        self._send(200, '<html><body><script src="/responsive-web/client-web/main.js"></script></body></html>', "text/html")

    def _graphql(self, path, payload):
        _, query_id, operation = path.rsplit("/", 2)
        if not self.headers.get("Authorization", "").startswith("Bearer AAAA") or self.headers.get("X-Csrf-Token") != CSRF:
            return self._send(403, "{}", "application/json")
        status, answer = _answer(operation, query_id, payload["variables"])
        if not payload.get("features", {}).get("view_counts_everywhere_api_enabled"):
            answer = _without_views(answer)
        self._send(status, json.dumps(answer), "application/json")

    def _cookie(self, name):
        match = re.search(rf"(?:^|; ){name}=([^;]+)", self.headers.get("Cookie") or "")
        return match.group(1) if match else None

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass


def _answer(operation, query_id, variables):
    """X's answer to one web API request: (HTTP status, JSON)."""
    if operation == "UserByScreenName":
        return _user_answer(query_id, variables["screen_name"])
    if operation == "UserTweets":
        return 200, {"data": {"user": {"result": {"timeline": {"timeline": USER_TWEETS[variables.get("cursor")]}}}}}
    if operation == "SearchTimeline" and variables["rawQuery"] == "python":
        return 200, {"data": {"search_by_raw_query": {"search_timeline": {"timeline": SEARCH[variables.get("cursor")]}}}}
    if operation == "TweetDetail":
        thread = THREAD if variables["focalTweetId"] == "20" else {"instructions": []}
        return 200, {"data": {"threaded_conversation_with_injections_v2": thread}}
    return 400, {"errors": [{"message": "unexpected request"}]}


def _without_views(value):
    """X leaves view counts out unless the request turns on view_counts_everywhere_api_enabled."""
    if isinstance(value, dict):
        return {key: _without_views(item) for key, item in value.items() if key != "views"}
    if isinstance(value, list):
        return [_without_views(item) for item in value]
    return value


def _user_answer(query_id, screen_name):
    if screen_name == "busy":
        return 429, {"errors": [{"message": "Rate limit exceeded"}]}
    if screen_name == "expired":
        return 401, {"errors": [{"message": "Could not authenticate you"}]}
    if screen_name == "renamed" and query_id != "FreshId":
        return 404, {}
    if screen_name in ("NASA", "renamed"):
        return 200, {"data": {"user": {"result": NASA}}}
    return 200, {"data": {"user": {}}}


@pytest.fixture(scope="module")
def x_origin():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeX)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(autouse=True)
def fake_home(x_origin, monkeypatch):
    monkeypatch.setattr(x_page, "X_HOME_URL", f"{x_origin}/home")


def _save_cookies(**cookies):
    login_store.save_cookies(
        USER, "x", [{"name": name, "value": value, "domain": "127.0.0.1", "path": "/"} for name, value in cookies.items()]
    )


@pytest.fixture
def logged_in(local_store):
    _save_cookies(auth_token="abc", ct0=CSRF)


@pytest_asyncio.fixture
async def browser():
    yield
    await browser_session.shutdown()


@pytest.mark.asyncio
async def test_profile_is_read_through_xs_web_api_with_the_users_session(logged_in, browser):
    [profile] = await x_page.read(USER, "profile", {"username": "NASA"}, "account '@NASA'")

    assert profile == {
        "username": "NASA",
        "name": "NASA",
        "bio": "Explore the universe",
        "location": "Pale Blue Dot",
        "website": "https://nasa.gov",
        "followers": 92,
        "following": 180,
        "tweets": 73000,
        "likes": 16000,
        "verified": True,
        "joined": "2007-12-19T20:20:32.000Z",
        "url": "https://x.com/NASA",
    }


@pytest.mark.asyncio
async def test_a_renamed_query_id_is_taken_from_xs_own_website_script(logged_in, browser):
    [profile] = await x_page.read(USER, "profile", {"username": "renamed"}, "account '@renamed'")

    assert profile["username"] == "NASA"


@pytest.mark.asyncio
async def test_tweets_skip_the_pinned_tweet_and_follow_the_next_page(logged_in, browser):
    tweets = await x_page.read(USER, "tweets", {"username": "NASA", "limit": 3}, "account '@NASA'")

    assert [tweet["id"] for tweet in tweets] == ["101", "102", "103"]
    assert tweets[0] == {
        "id": "101",
        "url": "https://x.com/NASA/status/101",
        "author": "NASA",
        "name": "NASA name",
        "text": "First tweet",
        "posted_at": "2026-11-09T05:20:13.000Z",
        "likes": 5,
        "retweets": 2,
        "replies": 1,
        "views": 900,
        "is_retweet": False,
        "in_reply_to": "",
        "media": [{"type": "video", "url": "https://video/high.mp4"}],
        "quoted_tweet_url": "",
    }
    assert (tweets[1]["is_retweet"], tweets[1]["quoted_tweet_url"]) == (True, "https://x.com/i/status/555")
    assert tweets[2]["media"] == [{"type": "photo", "url": "https://pbs/photo.jpg"}]


@pytest.mark.asyncio
async def test_tweets_are_cut_to_the_limit(logged_in, browser):
    tweets = await x_page.read(USER, "tweets", {"username": "NASA", "limit": 1}, "account '@NASA'")

    assert [tweet["id"] for tweet in tweets] == ["101"]


@pytest.mark.asyncio
async def test_search_returns_matching_tweets_across_pages(logged_in, browser):
    tweets = await x_page.read(USER, "search", {"query": "python", "limit": 5}, "results for 'python'")

    assert [tweet["id"] for tweet in tweets] == ["101", "103"]


@pytest.mark.asyncio
async def test_thread_returns_the_tweet_then_its_replies(logged_in, browser):
    tweets = await x_page.read(USER, "thread", {"tweet_id": "20", "limit": 5}, "tweet 20")

    assert [(tweet["id"], tweet["in_reply_to"], tweet["views"]) for tweet in tweets] == [("20", "", 900), ("21", "20", 900)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "args", "target", "message"),
    [
        ("profile", {"username": "nobody"}, "account '@nobody'", "X has no account '@nobody'"),
        ("tweets", {"username": "nobody", "limit": 5}, "account '@nobody'", "X has no account '@nobody'"),
        ("thread", {"tweet_id": "1", "limit": 5}, "tweet 1", "X has no tweet 1"),
    ],
    ids=["profile", "tweets", "thread"],
)
async def test_unknown_account_or_tweet_is_reported_as_not_found(logged_in, browser, command, args, target, message):
    with pytest.raises(PageReadError, match=message):
        await x_page.read(USER, command, args, target)


@pytest.mark.asyncio
async def test_rate_limit_stops_with_a_wait_message(logged_in, browser):
    with pytest.raises(RateLimitedError, match="Wait at least 15 minutes"):
        await x_page.read(USER, "profile", {"username": "busy"}, "account '@busy'")


@pytest.mark.asyncio
async def test_rejected_session_asks_the_user_to_log_in_again(logged_in, browser):
    with pytest.raises(NotLoggedInError, match="X did not accept the saved session"):
        await x_page.read(USER, "profile", {"username": "expired"}, "account '@expired'")


@pytest.mark.asyncio
async def test_session_without_its_anti_forgery_cookie_asks_the_user_to_log_in_again(local_store, browser):
    _save_cookies(auth_token="abc")

    with pytest.raises(NotLoggedInError, match="X did not accept the saved session"):
        await x_page.read(USER, "profile", {"username": "NASA"}, "account '@NASA'")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cookies", [{"ct0": CSRF}, {"auth_token": "locked", "ct0": CSRF}], ids=["logged-out", "locked-account"]
)
async def test_login_or_account_check_page_asks_the_user_to_log_in(local_store, browser, cookies):
    _save_cookies(**cookies)

    with pytest.raises(NotLoggedInError, match="login or account check page"):
        await x_page.read(USER, "profile", {"username": "NASA"}, "account '@NASA'")
