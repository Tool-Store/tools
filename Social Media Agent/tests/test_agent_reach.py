import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import agent_reach
from command_runner import CommandResult
from errors import AgentReachError


@pytest.fixture
def fake_run(monkeypatch):
    """Replace the real command with a recorder that returns a chosen Agent Reach reply."""
    calls = []
    reply = {"stdout": json.dumps({"ok": True, "items": []}), "exit_code": 0}

    def run(argv):
        calls.append(argv)
        return CommandResult(exit_code=reply["exit_code"], stdout=reply["stdout"], stderr="")

    monkeypatch.setattr(agent_reach, "run_command", run)
    return calls, reply


def _set_reply(reply, payload, exit_code=0):
    reply["stdout"] = payload if isinstance(payload, str) else json.dumps(payload)
    reply["exit_code"] = exit_code


def test_action_builds_browser_only_command_and_returns_items(fake_run):
    calls, reply = fake_run
    _set_reply(reply, {"ok": True, "items": [{"title": "Lead Python Engineer"}]})

    items = agent_reach.run_action("linkedin", "jobs", ["python developer"], {"limit": 2, "location": None})

    assert items == [{"title": "Lead Python Engineer"}]
    assert calls == [["agent-reach", "linkedin", "jobs", "python developer", "--limit", "2", "--backend", "opencli"]]


def test_x_uses_agent_reach_twitter_channel(fake_run):
    calls, _ = fake_run

    agent_reach.run_action("x", "profile", ["OpenAI"])

    assert calls[0][:3] == ["agent-reach", "twitter", "profile"]


def test_missing_items_return_empty_list(fake_run):
    _, reply = fake_run
    _set_reply(reply, {"ok": True})

    assert agent_reach.run_action("facebook", "profile", ["natgeo"]) == []


def test_need_login_error_tells_caller_to_start_login(fake_run):
    _, reply = fake_run
    _set_reply(reply, {"ok": False, "error": {"code": "NEED_LOGIN", "message": "signed-in session required"}}, 1)

    with pytest.raises(AgentReachError, match="Call start_login with site 'linkedin'") as error:
        agent_reach.run_action("linkedin", "jobs", ["python"])
    assert error.value.code == "NEED_LOGIN"


def test_other_error_keeps_code_and_message(fake_run):
    _, reply = fake_run
    _set_reply(reply, {"ok": False, "error": {"code": "UPSTREAM_BROKEN", "message": "browser did not open"}}, 1)

    with pytest.raises(AgentReachError, match=r"linkedin jobs failed \(UPSTREAM_BROKEN\): browser did not open") as error:
        agent_reach.run_action("linkedin", "jobs", ["python"])
    assert error.value.code == "UPSTREAM_BROKEN"


def test_unreadable_reply_raises_clear_error(fake_run):
    _, reply = fake_run
    _set_reply(reply, "Traceback (most recent call last): ...", 1)

    with pytest.raises(AgentReachError, match="unreadable reply for facebook search") as error:
        agent_reach.run_action("facebook", "search", ["openai"])
    assert error.value.code == agent_reach.UNREADABLE_REPLY


@pytest.mark.parametrize("payload", ['["x"]', '"text"', "null", "42"], ids=["list", "string", "null", "number"])
def test_reply_that_is_not_a_json_object_raises_clear_error(fake_run, payload):
    _, reply = fake_run
    _set_reply(reply, payload)

    with pytest.raises(AgentReachError, match="unreadable reply for linkedin jobs") as error:
        agent_reach.run_action("linkedin", "jobs", ["python"])
    assert error.value.code == agent_reach.UNREADABLE_REPLY


@pytest.mark.parametrize("items", [{}, [1], ["text"], [{"title": "ok"}, None]], ids=["object", "numbers", "strings", "mixed"])
def test_items_that_are_not_a_list_of_objects_raise_clear_error(fake_run, items):
    _, reply = fake_run
    _set_reply(reply, {"ok": True, "items": items})

    with pytest.raises(AgentReachError, match="unexpected format for x tweets") as error:
        agent_reach.run_action("x", "tweets", ["OpenAI"])
    assert error.value.code == agent_reach.UNREADABLE_REPLY


@pytest.mark.parametrize(
    ("hint", "wait"),
    [
        ("Wait 3583 seconds before retrying this channel.", "60 minutes"),
        ("Wait 30 seconds before retrying this channel.", "1 minute"),
        ("The platform reported a rate limit. Reach pauses this channel.", "about an hour"),
        (None, "about an hour"),
    ],
    ids=["paused-hour", "paused-seconds", "first-limit", "no-hint"],
)
def test_rate_limit_tells_caller_how_long_to_wait(fake_run, hint, wait):
    _, reply = fake_run
    _set_reply(reply, {"ok": False, "error": {"code": "RATE_LIMITED", "message": "HTTP 429", "hint": hint}}, 1)

    with pytest.raises(AgentReachError, match=f"Retry in {wait}, not sooner") as error:
        agent_reach.run_action("facebook", "profile", ["natgeo"])
    assert error.value.code == "RATE_LIMITED"


@pytest.mark.parametrize("code", ["UPSTREAM_BROKEN", "TIMEOUT", "PLATFORM_BLOCKED", "NOT_FOUND", "BAD_INPUT", "NEED_SETUP"])
def test_every_other_error_code_is_kept_with_its_message(fake_run, code):
    _, reply = fake_run
    _set_reply(reply, {"ok": False, "error": {"code": code, "message": "details here"}}, 1)

    with pytest.raises(AgentReachError, match=rf"facebook profile failed \({code}\): details here") as error:
        agent_reach.run_action("facebook", "profile", ["nasa"])
    assert error.value.code == code


def test_error_without_code_is_reported_as_unknown(fake_run):
    _, reply = fake_run
    _set_reply(reply, {"ok": False}, 1)

    with pytest.raises(AgentReachError, match=r"\(UNKNOWN\): no details"):
        agent_reach.run_action("facebook", "profile", ["nasa"])


def test_agent_reach_commands_never_run_at_the_same_time(monkeypatch):
    running = []
    most_at_once = []

    def slow_run(argv):
        running.append(argv)
        most_at_once.append(len(running))
        time.sleep(0.05)
        running.remove(argv)
        return CommandResult(exit_code=0, stdout=json.dumps({"ok": True, "items": []}), stderr="")

    monkeypatch.setattr(agent_reach, "run_command", slow_run)

    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda index: agent_reach.run_action("x", "profile", [f"user{index}"]), range(5)))

    assert max(most_at_once) == 1


def test_open_login_runs_login_command(fake_run):
    calls, reply = fake_run
    _set_reply(reply, {"ok": True, "items": [{"opened": "https://www.linkedin.com/login"}]})

    agent_reach.open_login("linkedin")

    assert calls == [["agent-reach", "login", "linkedin"]]


def test_open_login_failure_raises(fake_run):
    _, reply = fake_run
    _set_reply(reply, {"ok": False, "error": {"code": "UPSTREAM_BROKEN", "message": "browser closed"}}, 1)

    with pytest.raises(AgentReachError, match="x login failed"):
        agent_reach.open_login("x")
