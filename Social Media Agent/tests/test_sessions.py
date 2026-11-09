import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

import sessions
import user_store
from caller import Caller
from constants import (
    DAILY_REQUEST_LIMIT_ENV,
    DEFAULT_VIEWER_URL,
    INSTAGRAM_DAILY_REQUEST_LIMIT_ENV,
    VIEWER_URL_ENV,
    X_DAILY_REQUEST_LIMIT_ENV,
)
from errors import DailyLimitError, LoginBusyError, LoginTimeoutError, RateLimitedError

USER = Caller("user-1")
OTHER = Caller("user-2")


@pytest.fixture
def usage(local_store, monkeypatch):
    monkeypatch.setenv(DAILY_REQUEST_LIMIT_ENV, "2")
    monkeypatch.setattr(sessions, "_today", lambda: "2026-11-02")
    return local_store


def _saved_counts(caller=USER):
    return user_store.load(caller, "usage")["counts"]


def test_requests_are_counted_per_site_and_saved(usage):
    assert sessions.count_request(USER, "linkedin") == 1
    assert sessions.count_request(USER, "facebook") == 1
    assert sessions.count_request(USER, "linkedin") == 0

    assert user_store.load(USER, "usage") == {"date": "2026-11-02", "counts": {"linkedin": 2, "facebook": 1}}


def test_request_over_daily_limit_is_rejected_and_not_counted(usage):
    sessions.count_request(USER, "linkedin")
    sessions.count_request(USER, "linkedin")

    with pytest.raises(DailyLimitError, match="Daily limit of 2 requests for linkedin reached"):
        sessions.count_request(USER, "linkedin")
    assert _saved_counts()["linkedin"] == 2


def test_parallel_requests_are_all_counted(usage, monkeypatch):
    monkeypatch.setenv(DAILY_REQUEST_LIMIT_ENV, "100")

    with ThreadPoolExecutor(max_workers=10) as pool:
        remaining = list(pool.map(lambda site: sessions.count_request(USER, site), ["linkedin"] * 40))

    assert sorted(remaining) == list(range(60, 100))
    assert _saved_counts()["linkedin"] == 40


def test_parallel_requests_never_exceed_the_limit(usage):
    def try_request(_):
        try:
            sessions.count_request(USER, "facebook")
            return True
        except DailyLimitError:
            return False

    with ThreadPoolExecutor(max_workers=10) as pool:
        allowed = list(pool.map(try_request, range(10)))

    assert allowed.count(True) == 2
    assert _saved_counts()["facebook"] == 2


def test_count_resets_on_a_new_day(usage, monkeypatch):
    sessions.count_request(USER, "linkedin")
    sessions.count_request(USER, "linkedin")

    monkeypatch.setattr(sessions, "_today", lambda: "2026-11-03")

    assert sessions.count_request(USER, "linkedin") == 1


def test_unreadable_usage_record_starts_a_new_count(usage):
    sessions.count_request(USER, "facebook")
    [record] = [path for path in usage.rglob("usage.json")]
    record.write_text("not json")

    assert sessions.count_request(USER, "facebook") == 1


@pytest.mark.parametrize(
    "damaged",
    ["text", {"date": "2026-11-02"}, {"date": "2026-11-02", "counts": [1]}, {"date": "2026-11-02", "counts": {}, "last_call": 5}],
)
def test_usage_record_of_the_wrong_shape_starts_a_new_count(usage, damaged):
    user_store.save(USER, "usage", damaged)

    assert sessions.count_request(USER, "linkedin") == 1


@pytest.mark.parametrize("raw_limit", ["0", "-1", "many"])
def test_invalid_daily_limit_setting_is_rejected(usage, monkeypatch, raw_limit):
    monkeypatch.setenv(DAILY_REQUEST_LIMIT_ENV, raw_limit)

    with pytest.raises(ValueError, match=f"{DAILY_REQUEST_LIMIT_ENV} must be a whole number"):
        sessions.count_request(USER, "linkedin")


def test_start_login_opens_login_and_returns_viewer_link(monkeypatch):
    opened = []
    monkeypatch.setattr(sessions.agent_reach, "open_login", opened.append)
    monkeypatch.delenv(VIEWER_URL_ENV, raising=False)

    result = sessions.start_login("linkedin")

    assert opened == ["linkedin"]
    assert result["viewer_url"] == DEFAULT_VIEWER_URL
    assert "log in to linkedin" in result["next"]


def test_start_login_uses_configured_viewer_link(monkeypatch):
    monkeypatch.setattr(sessions.agent_reach, "open_login", lambda site: None)
    monkeypatch.setenv(VIEWER_URL_ENV, "https://viewer.example/u/123")

    assert sessions.start_login("facebook")["viewer_url"] == "https://viewer.example/u/123"


def test_each_user_has_their_own_daily_limit(usage):
    sessions.count_request(USER, "linkedin")
    sessions.count_request(USER, "linkedin")

    assert sessions.count_request(OTHER, "linkedin") == 1
    with pytest.raises(DailyLimitError):
        sessions.count_request(USER, "linkedin")


@pytest.fixture
def browser_login(monkeypatch):
    """Replace the visible login window with one that the test finishes."""
    finished = asyncio.Event()
    saved = []

    async def wait_for_login(login_url, login_cookie, timeout_seconds, poll_seconds):
        await finished.wait()
        if login_cookie == "fail":
            raise LoginTimeoutError("Login was not finished within 10 minutes.")
        return [{"name": login_cookie, "value": "session", "opened": login_url}]

    monkeypatch.setattr(sessions.browser_session, "wait_for_login", wait_for_login)
    monkeypatch.setattr(sessions.login_store, "save_cookies", lambda *args: saved.append(args))
    monkeypatch.setattr(sessions, "_login_task", None)
    return finished, saved


@pytest.mark.asyncio
async def test_browser_login_saves_the_users_cookies_once_they_log_in(browser_login, monkeypatch):
    finished, saved = browser_login
    monkeypatch.delenv(VIEWER_URL_ENV, raising=False)

    reply = await sessions.start_browser_login(USER, "linkedin")
    assert reply["viewer_url"] == DEFAULT_VIEWER_URL
    assert "saved automatically" in reply["next"]
    assert saved == []

    finished.set()
    await sessions._login_task

    assert saved == [(USER, "linkedin", [{"name": "li_at", "value": "session", "opened": "https://www.linkedin.com/login"}])]


@pytest.mark.asyncio
async def test_second_login_while_one_is_open_is_refused(browser_login):
    finished, _ = browser_login
    await sessions.start_browser_login(USER, "linkedin")

    with pytest.raises(LoginBusyError, match="Another login is open"):
        await sessions.start_browser_login(OTHER, "linkedin")

    finished.set()
    await sessions._login_task
    await sessions.start_browser_login(OTHER, "linkedin")
    await sessions._login_task


@pytest.mark.asyncio
async def test_unfinished_login_is_logged_and_nothing_is_saved(browser_login, monkeypatch, caplog):
    finished, saved = browser_login
    monkeypatch.setitem(sessions.BROWSER_LOGIN_PAGES, "linkedin", ("https://www.linkedin.com/login", "fail"))

    await sessions.start_browser_login(USER, "linkedin")
    finished.set()
    await sessions._login_task

    assert saved == []
    assert "The linkedin login did not finish" in caplog.text


def test_a_call_that_loads_several_pages_counts_each_page(usage, monkeypatch):
    monkeypatch.setenv(DAILY_REQUEST_LIMIT_ENV, "10")

    assert sessions.count_request(USER, "linkedin", page_loads=6) == 4
    assert _saved_counts()["linkedin"] == 6


def test_a_call_that_would_go_over_the_limit_is_refused_and_not_counted(usage, monkeypatch):
    monkeypatch.setenv(DAILY_REQUEST_LIMIT_ENV, "10")
    sessions.count_request(USER, "linkedin", page_loads=8)

    with pytest.raises(DailyLimitError, match="needs 3 page loads but only 2 of 10 are left"):
        sessions.count_request(USER, "linkedin", page_loads=3)
    assert _saved_counts()["linkedin"] == 8
    assert sessions.count_request(USER, "linkedin", page_loads=2) == 0


def test_instagram_has_its_own_lower_limit(usage, monkeypatch):
    monkeypatch.delenv(INSTAGRAM_DAILY_REQUEST_LIMIT_ENV, raising=False)

    assert sessions.count_request(USER, "instagram", page_loads=3) == 17
    assert sessions.count_request(USER, "facebook") == 1


def test_x_has_its_own_limit_from_its_own_setting(usage, monkeypatch):
    monkeypatch.delenv(X_DAILY_REQUEST_LIMIT_ENV, raising=False)
    assert sessions.count_request(USER, "x") == 29

    monkeypatch.setenv(X_DAILY_REQUEST_LIMIT_ENV, "1")
    with pytest.raises(DailyLimitError, match="Daily limit of 1 requests for x reached"):
        sessions.count_request(USER, "x")


def test_x_calls_closer_together_than_the_minimum_gap_are_refused_and_not_counted(usage, monkeypatch):
    monkeypatch.setattr(sessions, "_now", lambda: 1_000.0)
    sessions.count_request(USER, "x")

    monkeypatch.setattr(sessions, "_now", lambda: 1_004.0)
    with pytest.raises(RateLimitedError, match="Wait 6 more seconds before the next x call"):
        sessions.count_request(USER, "x")
    assert _saved_counts()["x"] == 1

    monkeypatch.setattr(sessions, "_now", lambda: 1_010.0)
    sessions.count_request(USER, "x")
    assert _saved_counts()["x"] == 2


def test_sites_without_a_minimum_gap_may_be_called_back_to_back(usage, monkeypatch):
    monkeypatch.setattr(sessions, "_now", lambda: 1_000.0)

    sessions.count_request(USER, "linkedin")
    sessions.count_request(USER, "linkedin")

    assert _saved_counts()["linkedin"] == 2


def test_instagram_limit_comes_from_its_own_setting(usage, monkeypatch):
    monkeypatch.setenv(INSTAGRAM_DAILY_REQUEST_LIMIT_ENV, "4")

    sessions.count_request(USER, "instagram", page_loads=4)
    with pytest.raises(DailyLimitError, match="Daily limit of 4 requests for instagram reached"):
        sessions.count_request(USER, "instagram")
