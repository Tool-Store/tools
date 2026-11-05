"""Runs Agent Reach commands and turns their JSON replies into items or clear errors."""

import json
import logging
import re
import threading
from typing import Any, Dict, List, Optional

from command_runner import CommandResult, run_command
from constants import AGENT_REACH_BINARY, FACEBOOK, LINKEDIN, X
from errors import AgentReachError, login_needed_message

log = logging.getLogger(__name__)

# Agent Reach channel and action names. X is still "twitter" in Agent Reach.
CHANNELS = {LINKEDIN: "linkedin", FACEBOOK: "facebook", X: "twitter"}
LOGIN = "login"
JOB_SEARCH = "jobs"
JOB_READ = "read"
SEARCH = "search"
PROFILE = "profile"
THREAD = "thread"
POSTS = {X: "tweets"}

BROWSER_BACKEND = "opencli"

NEED_LOGIN = "NEED_LOGIN"
RATE_LIMITED = "RATE_LIMITED"
UNREADABLE_REPLY = "UNREADABLE_REPLY"
WAIT_SECONDS_PATTERN = re.compile(r"Wait (\d+) seconds")

# All actions share one browser profile, so commands run one at a time.
_browser_lock = threading.Lock()


def run_action(
    site: str,
    action: str,
    arguments: List[str],
    options: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Run one site action and return its items."""
    argv = [AGENT_REACH_BINARY, CHANNELS[site], action, *arguments, *_option_words(options or {})]
    argv += ["--backend", BROWSER_BACKEND]
    with _browser_lock:
        result = run_command(argv)
    return _items_from(site, action, _read_reply(site, action, result))


def open_login(site: str) -> None:
    """Open the site's login page in the user's browser."""
    with _browser_lock:
        result = run_command([AGENT_REACH_BINARY, LOGIN, CHANNELS[site]])
    _read_reply(site, LOGIN, result)


def _option_words(options: Dict[str, Any]) -> List[str]:
    words: List[str] = []
    for name, value in options.items():
        if value is not None:
            words += [f"--{name}", str(value)]
    return words


def _read_reply(site: str, action: str, result: CommandResult) -> Dict[str, Any]:
    try:
        reply = json.loads(result.stdout)
    except json.JSONDecodeError:
        reply = None
    if not isinstance(reply, dict):
        log.warning("Unreadable Agent Reach reply for %s %s (exit %s): %s", site, action, result.exit_code, result.stderr)
        raise AgentReachError(
            UNREADABLE_REPLY,
            f"Agent Reach returned an unreadable reply for {site} {action} (exit code {result.exit_code}).",
        )
    if not reply.get("ok"):
        raise _error_from_reply(site, action, reply.get("error") or {})
    return reply


def _items_from(site: str, action: str, reply: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = reply.get("items")
    if items is None:
        return []
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        log.warning("Agent Reach items for %s %s are not a list of objects: %r", site, action, items)
        raise AgentReachError(UNREADABLE_REPLY, f"Agent Reach returned results in an unexpected format for {site} {action}.")
    return items


def _error_from_reply(site: str, action: str, error: Dict[str, Any]) -> AgentReachError:
    code = error.get("code") or "UNKNOWN"
    if code == NEED_LOGIN:
        return AgentReachError(code, login_needed_message(site, "Not logged in to"))
    log.warning("Agent Reach %s %s failed with %s: %s", site, action, code, error.get("message"))
    if code == RATE_LIMITED:
        return AgentReachError(
            code,
            f"{site} reported too many requests, so it is paused to protect the account. "
            f"Retry in {_wait_text(error.get('hint') or '')}, not sooner.",
        )
    return AgentReachError(code, f"{site} {action} failed ({code}): {error.get('message') or 'no details'}")


def _wait_text(hint: str) -> str:
    match = WAIT_SECONDS_PATTERN.search(hint)
    if not match:
        return "about an hour"
    minutes = max(1, round(int(match.group(1)) / 60))
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
