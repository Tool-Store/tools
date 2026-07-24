"""Shared helpers for CLI Runner manual verification scripts.

Mirrors tools/Gmail/scripts/_common.py: PASS/FAIL assertions, shared helpers.
Uses a temp install-state file so tests never touch /app/data.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any

_CLI_RUNNER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _CLI_RUNNER_DIR)

# Must be set before importing cli_runtime (STATE_PATH is read at import time).
_DEFAULT_STATE = os.path.join(tempfile.gettempdir(), "cli-runner-test-state.json")
os.environ.setdefault("CLI_RUNNER_STATE_PATH", os.environ.get("CLI_RUNNER_TEST_STATE_FILE", _DEFAULT_STATE))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(os.path.join(_CLI_RUNNER_DIR, ".env"))

from cli_runtime import (  # noqa: E402
    CliRuntimeError,
    check_binary,
    get_install_status,
    install_skill_runtime,
    run_cli_command,
)

STATE_FILE = os.environ["CLI_RUNNER_STATE_PATH"]


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


def reset_install_state() -> None:
    """Clear install-state file so lifecycle tests start clean."""
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    step(f"cleared install state at {STATE_FILE}")


__all__ = [
    "CliRuntimeError",
    "STATE_FILE",
    "assert_ok",
    "check_binary",
    "fail",
    "get_install_status",
    "install_skill_runtime",
    "ok",
    "pretty",
    "reset_install_state",
    "run_cli_command",
    "section",
    "step",
]
