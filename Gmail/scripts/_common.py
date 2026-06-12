"""Shared helpers for Gmail manual verification scripts.

Each script reads a Google OAuth access token from the GOOGLE_ACCESS_TOKEN env var,
exercises a slice of GmailClient functionality, and prints PASS/FAIL per assertion.

State (e.g. ids produced by earlier scripts) is persisted in /tmp/gmail_test_state.json
so scripts can run independently and pick up where the previous one left off.
"""

import json
import os
import sys
import time
from typing import Any, Dict, Optional

_GMAIL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _GMAIL_DIR)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(os.path.join(_GMAIL_DIR, ".env"))

from gmail import GmailClient  # noqa: E402


TARGET_EMAIL = os.environ.get("GMAIL_TEST_RECIPIENT", "lilua.brainerhub@gmail.com")
STATE_FILE = os.environ.get("GMAIL_TEST_STATE_FILE", "/tmp/gmail_test_state.json")


def get_client() -> GmailClient:
    token = os.environ.get("GOOGLE_ACCESS_TOKEN")
    if not token:
        sys.stderr.write(
            "ERROR: GOOGLE_ACCESS_TOKEN env var is required.\n"
            "       Get a token from https://developers.google.com/oauthplayground/\n"
            "       with scope https://www.googleapis.com/auth/gmail.modify, then run:\n"
            '       GOOGLE_ACCESS_TOKEN="ya29...." python <script>.py\n'
        )
        sys.exit(2)
    return GmailClient(token)


def now_marker(prefix: str = "GmailToolTest") -> str:
    return f"{prefix}_{int(time.time())}"


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def step(message: str) -> None:
    print(f"-> {message}")


def ok(message: str) -> None:
    print(f"   PASS: {message}")


def fail(message: str) -> None:
    sys.stderr.write(f"   FAIL: {message}\n")
    sys.exit(1)


def assert_ok(condition: bool, message: str) -> None:
    if condition:
        ok(message)
    else:
        fail(message)


def pretty(value: Any) -> None:
    if isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2, default=str))
    else:
        print(value)


# -----------------------------------------------------------------------------
# Cross-script state
# -----------------------------------------------------------------------------
def _load_all_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save_state(key: str, value: Any) -> None:
    data = _load_all_state()
    data[key] = value
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_state(key: str) -> Optional[Any]:
    return _load_all_state().get(key)


def require_state(key: str, missing_hint: str) -> Any:
    value = load_state(key)
    if value is None:
        sys.stderr.write(f"ERROR: missing test state '{key}'. {missing_hint}\n")
        sys.exit(2)
    return value
