import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

import sessions
from constants import (
    DAILY_REQUEST_LIMIT_ENV,
    DEFAULT_VIEWER_URL,
    USAGE_FILE_ENV,
    VIEWER_URL_ENV,
)
from errors import DailyLimitError, LoginBusyError, LoginTimeoutError


@pytest.fixture
def usage_file(tmp_path, monkeypatch):
    path = tmp_path / "usage.json"
    monkeypatch.setenv(USAGE_FILE_ENV, str(path))
    monkeypatch.setenv(DAILY_REQUEST_LIMIT_ENV, "2")
    monkeypatch.setattr(sessions, "_today", lambda: "2026-11-02")
    return path


def test_requests_are_counted_per_site_and_saved(usage_file):
    assert sessions.count_request("user-1", "linkedin") == 1
    assert sessions.count_request("user-1", "x") == 1
    assert sessions.count_request("user-1", "linkedin") == 0

    assert json.loads(usage_file.read_text()) == {"date": "2026-11-02", "counts": {"user-1": {"linkedin": 2, "x": 1}}}


def test_request_over_daily_limit_is_rejected_and_not_counted(usage_file):
    sessions.count_request("user-1", "linkedin")
    sessions.count_request("user-1", "linkedin")

    with pytest.raises(DailyLimitError, match="Daily limit of 2 requests for linkedin reached"):
        sessions.count_request("user-1", "linkedin")
    assert json.loads(usage_file.read_text())["counts"]["user-1"]["linkedin"] == 2


def test_parallel_requests_are_all_counted(usage_file, monkeypatch):
    monkeypatch.setenv(DAILY_REQUEST_LIMIT_ENV, "100")

    with ThreadPoolExecutor(max_workers=10) as pool:
        remaining = list(pool.map(lambda site: sessions.count_request("user-1", site), ["linkedin"] * 40))

    assert sorted(remaining) == list(range(60, 100))
    assert json.loads(usage_file.read_text())["counts"]["user-1"]["linkedin"] == 40


def test_parallel_requests_never_exceed_the_limit(usage_file):
    def try_request(_):
        try:
            sessions.count_request("user-1", "x")
            return True
        except DailyLimitError:
            return False

    with ThreadPoolExecutor(max_workers=10) as pool:
        allowed = list(pool.map(try_request, range(10)))

    assert allowed.count(True) == 2
    assert json.loads(usage_file.read_text())["counts"]["user-1"]["x"] == 2


def test_count_resets_on_a_new_day(usage_file, monkeypatch):
    sessions.count_request("user-1", "linkedin")
    sessions.count_request("user-1", "linkedin")

    monkeypatch.setattr(sessions, "_today", lambda: "2026-11-03")

    assert sessions.count_request("user-1", "linkedin") == 1


def test_unreadable_usage_file_starts_a_new_count(usage_file):
    usage_file.write_text("not json")

    assert sessions.count_request("user-1", "instagram") == 1


@pytest.mark.parametrize("raw_limit", ["0", "-1", "many"])
def test_invalid_daily_limit_setting_is_rejected(usage_file, monkeypatch, raw_limit):
    monkeypatch.setenv(DAILY_REQUEST_LIMIT_ENV, raw_limit)

    with pytest.raises(ValueError, match=f"{DAILY_REQUEST_LIMIT_ENV} must be a whole number"):
        sessions.count_request("user-1", "linkedin")


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

    assert sessions.start_login("x")["viewer_url"] == "https://viewer.example/u/123"


def test_each_user_has_their_own_daily_limit(usage_file):
    sessions.count_request("user-1", "linkedin")
    sessions.count_request("user-1", "linkedin")

    assert sessions.count_request("user-2", "linkedin") == 1
    with pytest.raises(DailyLimitError):
        sessions.count_request("user-1", "linkedin")


def test_usage_file_from_before_per_user_counts_is_replaced(usage_file):
    usage_file.write_text(json.dumps({"date": "2026-11-02", "counts": {"user-1": 5}}))

    assert sessions.count_request("user-1", "linkedin") == 1


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

    reply = await sessions.start_browser_login("user-1", "linkedin")
    assert reply["viewer_url"] == DEFAULT_VIEWER_URL
    assert "saved automatically" in reply["next"]
    assert saved == []

    finished.set()
    await sessions._login_task

    assert saved == [("user-1", "linkedin", [{"name": "li_at", "value": "session", "opened": "https://www.linkedin.com/login"}])]


@pytest.mark.asyncio
async def test_second_login_while_one_is_open_is_refused(browser_login):
    finished, _ = browser_login
    await sessions.start_browser_login("user-1", "linkedin")

    with pytest.raises(LoginBusyError, match="Another login is open"):
        await sessions.start_browser_login("user-2", "linkedin")

    finished.set()
    await sessions._login_task
    await sessions.start_browser_login("user-2", "linkedin")
    await sessions._login_task


@pytest.mark.asyncio
async def test_unfinished_login_is_logged_and_nothing_is_saved(browser_login, monkeypatch, caplog):
    finished, saved = browser_login
    monkeypatch.setitem(sessions.BROWSER_LOGIN_PAGES, "linkedin", ("https://www.linkedin.com/login", "fail"))

    await sessions.start_browser_login("user-1", "linkedin")
    finished.set()
    await sessions._login_task

    assert saved == []
    assert "The linkedin login did not finish" in caplog.text


def test_a_call_that_loads_several_pages_counts_each_page(usage_file, monkeypatch):
    monkeypatch.setenv(DAILY_REQUEST_LIMIT_ENV, "10")

    assert sessions.count_request("user-1", "linkedin", page_loads=6) == 4
    assert json.loads(usage_file.read_text())["counts"]["user-1"]["linkedin"] == 6


def test_a_call_that_would_go_over_the_limit_is_refused_and_not_counted(usage_file, monkeypatch):
    monkeypatch.setenv(DAILY_REQUEST_LIMIT_ENV, "10")
    sessions.count_request("user-1", "linkedin", page_loads=8)

    with pytest.raises(DailyLimitError, match="needs 3 page loads but only 2 of 10 are left"):
        sessions.count_request("user-1", "linkedin", page_loads=3)
    assert json.loads(usage_file.read_text())["counts"]["user-1"]["linkedin"] == 8
    assert sessions.count_request("user-1", "linkedin", page_loads=2) == 0
